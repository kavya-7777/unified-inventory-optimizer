"""API v1 router — Demand Ingestion and Retrieval."""
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import require_api_key
from app.db.deps import get_db
from app.repositories.demand import DemandRepository
from app.schemas.demand import DemandHistoryOut, DemandIngestRequest, DemandIngestResponse

router = APIRouter(prefix="/api/v1/demand", tags=["demand"])


@router.post(
    "/ingest",
    response_model=DemandIngestResponse,
    dependencies=[Depends(require_api_key)],
)
def ingest_demand(payload: DemandIngestRequest, db: Session = Depends(get_db)):
    """
    Ingest a batch of historical demand records.
    Existing (location, product, date) rows have their quantity overwritten.
    """
    records = [record.model_dump() for record in payload.records]
    return DemandRepository(db).upsert_bulk(records)


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
