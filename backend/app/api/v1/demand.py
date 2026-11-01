"""API v1 router — Demand Ingestion and Retrieval."""
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_role
from app.db.deps import get_db
from app.forecasting.engine import forecast_series
from app.models.inventory import Location, Product
from app.repositories.demand import DemandRepository
from app.schemas.demand import (
    DemandForecastOut,
    DemandHistoryOut,
    DemandIngestRequest,
    DemandIngestResponse,
)
from app.services.users import record_event

router = APIRouter(prefix="/api/v1/demand", tags=["demand"])


@router.post("/ingest", response_model=DemandIngestResponse)
def ingest_demand(
    payload: DemandIngestRequest,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("planner")),
):
    """
    Ingest a batch of historical demand records.
    Existing (location, product, date) rows have their quantity overwritten.
    """
    records = [record.model_dump() for record in payload.records]
    result = DemandRepository(db).upsert_bulk(records)
    record_event(db, current, "demand.ingest", "demand_history", None,
                 {k: result[k] for k in ("inserted_count", "updated_count", "ignored_count")})
    return result


@router.get("/history", response_model=List[DemandHistoryOut])
def get_demand_history(
    location_id: str,
    product_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    """Demand history time series for a location and product, ordered chronologically."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date")
    return DemandRepository(db).get_history(
        location_id=location_id,
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
    )


@router.get("/forecast", response_model=DemandForecastOut)
def get_demand_forecast(
    location_id: str,
    product_id: str,
    horizon: int = Query(14, ge=1, le=90),
    history_days: int = Query(90, ge=14, le=730),
    db: Session = Depends(get_db),
):
    """
    Classifies the series, backtests every candidate model on a holdout window, and
    forecasts `horizon` days ahead with the most accurate one (95% prediction interval).
    """
    if not db.get(Location, location_id) or not db.get(Product, product_id):
        raise HTTPException(status_code=404, detail="Unknown location or product")
    repo = DemandRepository(db)
    dates, series = repo.get_daily_series(history_days, [product_id], [location_id])
    if not dates:
        raise HTTPException(status_code=404, detail="No demand history recorded yet")
    history = series.get((location_id, product_id), [0.0] * len(dates))
    result = forecast_series(history, horizon)

    backtest = []
    if result["backtest"]:
        test_dates = dates[-len(result["backtest"]["actual"]):]
        backtest = [
            {"date": d, "actual": a, "forecast": f}
            for d, a, f in zip(test_dates, result["backtest"]["actual"],
                               result["backtest"]["forecast"])
        ]
    future = [
        {"date": dates[-1] + timedelta(days=k + 1), "forecast": result["forecast"][k],
         "lower": result["lower"][k], "upper": result["upper"][k]}
        for k in range(horizon)
    ]
    return {
        **result,
        "location_id": location_id,
        "product_id": product_id,
        "history": [{"date": d, "quantity": q} for d, q in zip(dates, history)],
        "backtest": backtest,
        "forecast": future,
    }
