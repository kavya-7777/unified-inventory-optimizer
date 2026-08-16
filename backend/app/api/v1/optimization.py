"""API v1 router — Optimization and Pipeline runs."""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.repositories.pipeline import PipelineRunRepository
from app.schemas.optimization import OptimizationRunRequest, OptimizationRunResponse, PipelineRunOut, ForecastRunRequest
from app.services.optimization import trigger_optimization
from app.forecasting.runner import run_forecast_pipeline

router = APIRouter(prefix="/api/v1", tags=["optimization"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/optimization/run")
def run_optimization(payload: OptimizationRunRequest, db: Session = Depends(get_db)):
    try:
        return trigger_optimization(db, payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "SOLVER_ERROR", "message": str(e)})


@router.post("/forecast/run")
def run_forecast(payload: ForecastRunRequest):
    results = run_forecast_pipeline(payload.items, horizon=payload.horizon)
    return {"forecasts": results, "count": len(results)}


@router.get("/runs", response_model=List[PipelineRunOut])
def get_runs(limit: int = 10, db: Session = Depends(get_db)):
    return PipelineRunRepository(db).get_recent(limit=limit)


@router.get("/runs/{run_id}", response_model=PipelineRunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = PipelineRunRepository(db).get_by_id(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return run
