"""Service layer: bridges repositories and the optimization engine."""
import logging
from sqlalchemy.orm import Session
from app.repositories.pipeline import PipelineRunRepository, OptimizationResultRepository, AlertRepository
from app.optimization.runner import run_optimization_pipeline

log = logging.getLogger(__name__)


def trigger_optimization(db: Session, params: dict) -> dict:
    """
    Orchestrates a full optimization run with database persistence:
    1. Create pipeline_run record (status=running)
    2. Run the MEIO optimization engine
    3. Persist results and update pipeline_run (status=success/failed)
    4. Create alerts for any violations
    """
    run_repo = PipelineRunRepository(db)
    result_repo = OptimizationResultRepository(db)
    alert_repo = AlertRepository(db)

    # 1. Pre-generate run ID so DB and engine share the same UUID
    import uuid
    run_id = str(uuid.uuid4())
    params["pipeline_run_id"] = run_id

    run = run_repo.create(
        run_id=run_id,
        run_type=params.get("run_type", "manual"),
        parameters=params,
    )

    try:
        # 2. Run optimization (engine will use params["pipeline_run_id"])
        result = run_optimization_pipeline(params)

        # 3. Persist results (only if a real network map is provided)
        location_product_map = params.get("location_product_map") or {}
        if location_product_map:
            result_repo.bulk_save(
                pipeline_run_id=run_id,
                node_results=result.get("node_results", {}),
                location_product_map=location_product_map,
            )

        # 4. Create alerts for capacity violations
        for violation in result.get("capacity_violations", []):
            alert_repo.create(
                alert_type="CAPACITY_EXCEEDED",
                message=violation,
                severity="WARNING",
                pipeline_run_id=run_id,
            )

        # 5. Mark as complete
        run_repo.complete(
            run_id=run_id,
            status="success",
            solver=result.get("solver", "cp-sat"),
            fallback_used=result.get("fallback_used", False),
            duration=result.get("total_duration_seconds", 0),
        )

        return result

    except Exception as e:
        log.exception(f"Optimization pipeline failed: {e}")
        run_repo.fail(run_id=run_id, error=str(e))
        raise
