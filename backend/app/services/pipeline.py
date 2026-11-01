"""
End-to-end Pipeline Orchestration.
Chains Forecast -> GSM -> Transportation -> Alerts inside a single persisted run.
"""
import copy
import logging
import time
import uuid
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.forecasting.runner import run_forecast_pipeline
from app.models.base import utcnow
from app.optimization.errors import NetworkValidationError
from app.optimization.runner import (
    default_demo_edges,
    default_demo_nodes,
    run_optimization_pipeline,
)
from app.repositories.pipeline import AlertRepository, ForecastRepository, PipelineRunRepository
from app.services.optimization import stage_optimization_outputs, validate_references
from app.transportation.optimizer import optimize_transportation

log = logging.getLogger(__name__)


def run_daily_pipeline(
    db: Session, params: Dict[str, Any], triggered_by: Optional[str] = None
) -> Dict[str, Any]:
    validate_references(db, params.get("nodes") or [])
    run_id = str(uuid.uuid4())
    start = time.perf_counter()
    log.info(f"pipeline_run={run_id} starting end-to-end pipeline")

    run_repo = PipelineRunRepository(db)
    run_repo.create(
        run_id=run_id,
        run_type=params.get("run_type", "daily_batch"),
        parameters=params,
        triggered_by=triggered_by,
    )

    nodes = copy.deepcopy(params.get("nodes") or default_demo_nodes())
    edges = copy.deepcopy(params.get("edges") or default_demo_edges())
    items_history = params.get("items_history") or []
    stages: Dict[str, Dict[str, Any]] = {}

    try:
        if items_history:
            forecasts = run_forecast_pipeline(items_history, horizon=params.get("horizon", 4))
            by_id = {f["id"]: f for f in forecasts}
            for n in nodes:
                f = by_id.get(n["id"])
                if not f or not f["forecast"]:
                    continue
                n["demand_mean"] = sum(f["forecast"]) / len(f["forecast"])
                if not n.get("demand_std"):
                    n["demand_std"] = f["demand_std"]

            node_keys = {
                n["id"]: (n["location_id"], n["product_id"])
                for n in nodes
                if n.get("location_id") and n.get("product_id")
            }
            saved = ForecastRepository(db).bulk_save(run_id, forecasts, node_keys, utcnow())
            stages["forecast"] = {"status": "SUCCESS", "count": len(forecasts), "saved": saved}
        else:
            stages["forecast"] = {"status": "SKIPPED"}

        gsm_result = run_optimization_pipeline({
            **params,
            "pipeline_run_id": run_id,
            "nodes": nodes,
            "edges": edges,
        })
        stage_optimization_outputs(db, run_id, gsm_result)
        stages["gsm"] = {
            "status": gsm_result["status"],
            "solver": gsm_result["solver"],
            "fallback_used": gsm_result["fallback_used"],
            "objective_value": gsm_result["objective_value"],
        }

        transport_result = optimize_transportation(nodes, edges)
        stages["transportation"] = transport_result
        if transport_result["status"] == "INFEASIBLE":
            AlertRepository(db).create(
                alert_type="TRANSPORT_INFEASIBLE",
                message=f"Transportation LP failed to route freight: {transport_result['message']}",
                severity="CRITICAL",
                pipeline_run_id=run_id,
            )

        run_repo.complete(
            run_id=run_id,
            status="success",
            solver=gsm_result["solver"],
            fallback_used=gsm_result["fallback_used"],
            duration=round(time.perf_counter() - start, 4),
        )
    except NetworkValidationError as e:
        run_repo.fail(run_id=run_id, error=str(e))
        raise
    except Exception as e:
        log.exception(f"pipeline_run={run_id} failed")
        run_repo.fail(run_id=run_id, error=str(e))
        raise

    return {
        "pipeline_run_id": run_id,
        "status": "SUCCESS",
        "stages": stages,
        "node_results": gsm_result["node_results"],
    }
