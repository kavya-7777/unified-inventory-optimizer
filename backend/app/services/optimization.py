"""Service layer: bridges repositories and the optimization engine."""
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.inventory import Location, Product
from app.optimization.errors import NetworkValidationError
from app.optimization.runner import run_optimization_pipeline
from app.repositories.pipeline import (
    AlertRepository,
    OptimizationResultRepository,
    PipelineRunRepository,
)

log = logging.getLogger(__name__)


def validate_references(db: Session, nodes: List[Dict[str, Any]]) -> None:
    """Raises NetworkValidationError if nodes point at unknown locations or products."""
    errors: List[str] = []
    for column, key in ((Location.id, "location_id"), (Product.id, "product_id")):
        ids = {n[key] for n in nodes if n.get(key)}
        if not ids:
            continue
        known: Set[str] = set(db.scalars(select(column).where(column.in_(ids))))
        errors += [f"Unknown {key} '{x}'." for x in sorted(ids - known)]
    if errors:
        raise NetworkValidationError(errors)


def stage_optimization_outputs(db: Session, run_id: str, result: Dict[str, Any]) -> None:
    """Adds node results and capacity alerts to the session without committing."""
    OptimizationResultRepository(db).bulk_save(run_id, result["node_results"])
    alert_repo = AlertRepository(db)
    for violation in result["capacity_violations"]:
        alert_repo.create(
            alert_type="CAPACITY_EXCEEDED",
            message=violation,
            severity="WARNING",
            pipeline_run_id=run_id,
        )
    if result["fallback_used"]:
        alert_repo.create(
            alert_type="SOLVER_FALLBACK",
            message="CP-SAT found no solution in time; heuristic fallback was used.",
            severity="INFO",
            pipeline_run_id=run_id,
        )


def trigger_optimization(
    db: Session, params: Dict[str, Any], triggered_by: Optional[str] = None
) -> Dict[str, Any]:
    """Runs the optimizer inside a persisted pipeline run (running → success | failed)."""
    validate_references(db, params.get("nodes") or [])
    run_repo = PipelineRunRepository(db)
    run_id = str(uuid.uuid4())
    params = {**params, "pipeline_run_id": run_id}
    run_repo.create(run_id=run_id, run_type=params.get("run_type", "manual"), parameters=params,
                    triggered_by=triggered_by)

    try:
        result = run_optimization_pipeline(params)
        stage_optimization_outputs(db, run_id, result)
        run_repo.complete(
            run_id=run_id,
            status="success",
            solver=result["solver"],
            fallback_used=result["fallback_used"],
            duration=result["total_duration_seconds"],
        )
        return result
    except NetworkValidationError as e:
        run_repo.fail(run_id=run_id, error=str(e))
        raise
    except Exception as e:
        log.exception(f"pipeline_run={run_id} optimization failed")
        run_repo.fail(run_id=run_id, error=str(e))
        raise
