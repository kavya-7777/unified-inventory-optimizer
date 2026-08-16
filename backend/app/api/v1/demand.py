"""API v1 router — Demand Ingestion and Retrieval."""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.repositories.demand import DemandRepository
from app.schemas.demand import DemandIngestRequest, DemandIngestResponse, DemandHistoryOut

router = APIRouter(prefix="/api/v1/demand", tags=["demand"])


@router.post("/ingest", response_model=DemandIngestResponse)
def ingest_demand(payload: DemandIngestRequest, db: Session = Depends(get_db)):
    """
    Ingest a batch of historical demand records.
    Uses an upsert mechanism (overwrites quantity if location+product+date already exists).
    """
    repo = DemandRepository(db)
    
    # Convert Pydantic models to dicts for bulk insert
    records = [record.model_dump() for record in payload.records]
    
    try:
        result = repo.upsert_bulk(records)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest demand: {str(e)}")


@router.get("/history", response_model=List[DemandHistoryOut])
def get_demand_history(
    location_id: str,
    product_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Fetch demand history time series for a specific location and product.
    Ordered chronologically.
    """
    repo = DemandRepository(db)
    return repo.get_history(
        location_id=location_id, 
        product_id=product_id, 
        start_date=start_date, 
        end_date=end_date
    )
