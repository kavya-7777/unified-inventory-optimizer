"""API v1 router — Optimization and Pipeline runs."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.deps import get_db
from app.forecasting.runner import run_forecast_pipeline
from app.optimization.errors import NetworkValidationError
from app.repositories.pipeline import (
    AlertRepository,
    OptimizationResultRepository,
    PipelineRunRepository,
)
from app.schemas.optimization import (
    AlertOut,
    ForecastRunRequest,
    ForecastRunResponse,
    OptimizationResultOut,
    OptimizationRunRequest,
    OptimizationRunResponse,
    PipelineRunOut,
    PipelineRunRequest,
    PipelineRunResponse,
)
from app.services.optimization import trigger_optimization
from app.services.pipeline import run_daily_pipeline

router = APIRouter(prefix="/api/v1", tags=["optimization"])


def _invalid_network(e: NetworkValidationError) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": "INVALID_NETWORK", "errors": e.errors})


@router.post(
    "/optimization/run",
    response_model=OptimizationRunResponse,
    dependencies=[Depends(require_api_key)],
)
def run_optimization(payload: OptimizationRunRequest, db: Session = Depends(get_db)):
    try:
        return trigger_optimization(db, payload.model_dump())
    except NetworkValidationError as e:
        raise _invalid_network(e) from e


@router.post("/forecast/run", response_model=ForecastRunResponse)
def run_forecast(payload: ForecastRunRequest):
    items = [item.model_dump() for item in payload.items]
    results = run_forecast_pipeline(items, horizon=payload.horizon)
    return {"forecasts": results, "count": len(results)}


@router.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    dependencies=[Depends(require_api_key)],
)
def run_master_pipeline(payload: PipelineRunRequest, db: Session = Depends(get_db)):
    """Run the entire E2E pipeline: Validation -> Forecast -> GSM -> Transportation"""
    try:
        return run_daily_pipeline(db, payload.model_dump())
    except NetworkValidationError as e:
        raise _invalid_network(e) from e


@router.get("/runs", response_model=List[PipelineRunOut])
def get_runs(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return PipelineRunRepository(db).get_recent(skip=skip, limit=limit)


@router.get("/runs/{run_id}", response_model=PipelineRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = PipelineRunRepository(db).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run


@router.get("/runs/{run_id}/results", response_model=List[OptimizationResultOut])
def get_run_results(run_id: str, db: Session = Depends(get_db)):
    if not PipelineRunRepository(db).get_by_id(run_id):
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return OptimizationResultRepository(db).get_by_run(run_id)


@router.get("/alerts", response_model=List[AlertOut])
def get_alerts(
    resolved: Optional[bool] = None,
    run_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return AlertRepository(db).list_alerts(
        resolved=resolved, pipeline_run_id=run_id, skip=skip, limit=limit
    )


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertOut,
    dependencies=[Depends(require_api_key)],
)
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = AlertRepository(db).resolve(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert
