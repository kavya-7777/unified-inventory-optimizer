"""
End-to-end Pipeline Orchestration.
Chains Data Validation -> Forecast -> GSM -> Transportation -> Alerts.
"""
import logging
import uuid
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.repositories.pipeline import PipelineRunRepository, OptimizationResultRepository, AlertRepository
from app.optimization.runner import run_optimization_pipeline
from app.forecasting.runner import run_forecast_pipeline
from app.transportation.optimizer import optimize_transportation

log = logging.getLogger(__name__)

def run_daily_pipeline(db: Session, params: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    log.info(f"Starting end-to-end pipeline run {run_id}")
    
    run_repo = PipelineRunRepository(db)
    result_repo = OptimizationResultRepository(db)
    alert_repo = AlertRepository(db)
    
    run_repo.create(
        run_id=run_id,
        run_type=params.get("run_type", "daily_batch"),
        parameters=params,
    )
    
    pipeline_result = {
        "pipeline_run_id": run_id,
        "status": "RUNNING",
        "stages": {}
    }
    
    try:
        # 1. Validation & Setup
        nodes = params.get("nodes", [])
        edges = params.get("edges", [])
        items_history = params.get("items_history", [])
        
        # 2. Forecasting
        if items_history:
            forecasts = run_forecast_pipeline(items_history, horizon=params.get("horizon", 4))
            forecast_map = {f["id"]: sum(f["forecast"])/len(f["forecast"]) for f in forecasts if f["forecast"]}
            for n in nodes:
                if n["id"] in forecast_map:
                    n["demand_mean"] = forecast_map[n["id"]]
            pipeline_result["stages"]["forecast"] = {"status": "SUCCESS", "count": len(forecasts)}
        else:
            pipeline_result["stages"]["forecast"] = {"status": "SKIPPED"}
            
        # 3. GSM Optimization
        opt_params = dict(params)
        opt_params["pipeline_run_id"] = run_id
        opt_params["nodes"] = nodes
        opt_params["edges"] = edges
        gsm_result = run_optimization_pipeline(opt_params)
        
        if gsm_result["status"] not in ("OPTIMAL", "FEASIBLE"):
            raise ValueError(f"GSM Solver Failed: {gsm_result.get('errors') or gsm_result['status']}")
            
        pipeline_result["stages"]["gsm"] = {"status": "SUCCESS", "solver": gsm_result["solver"]}
        
        # Persist GSM Results
        if params.get("location_product_map"):
            result_repo.bulk_save(
                pipeline_run_id=run_id,
                node_results=gsm_result.get("node_results", {}),
                location_product_map=params.get("location_product_map")
            )
            
        for violation in gsm_result.get("capacity_violations", []):
            alert_repo.create(
                alert_type="CAPACITY_EXCEEDED",
                message=violation,
                severity="WARNING",
                pipeline_run_id=run_id
            )

        # 4. Transportation Optimization
        transport_result = optimize_transportation(nodes, edges)
        pipeline_result["stages"]["transportation"] = {
            "status": transport_result["status"],
            "total_cost": transport_result.get("total_cost"),
            "flows": transport_result.get("flows")
        }
        
        if transport_result["status"] == "INFEASIBLE":
            alert_repo.create(
                alert_type="TRANSPORT_INFEASIBLE",
                message=f"Transportation LP failed to route freight: {transport_result.get('message')}",
                severity="CRITICAL",
                pipeline_run_id=run_id
            )
            
        # Complete
        pipeline_result["status"] = "SUCCESS"
        run_repo.complete(
            run_id=run_id,
            status="success",
            solver=gsm_result.get("solver", "cp-sat"),
            fallback_used=gsm_result.get("fallback_used", False),
            duration=gsm_result.get("total_duration_seconds", 0)
        )
        return pipeline_result

    except Exception as e:
        log.exception(f"Pipeline failed: {e}")
        pipeline_result["status"] = "FAILED"
        pipeline_result["error"] = str(e)
        run_repo.fail(run_id=run_id, error=str(e))
        return pipeline_result
