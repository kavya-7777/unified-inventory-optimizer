"""API v1 router — Transportation lane-flow plan (multi-SKU LP)."""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.transportation import TransportationPlanOut
from app.services.transportation import build_transportation_plan

router = APIRouter(prefix="/api/v1", tags=["transportation"])


@router.get("/transportation/plan", response_model=TransportationPlanOut)
def get_transportation_plan(
    product_id: Optional[str] = None,
    days: int = Query(28, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Min-cost lane x SKU flows covering trailing average Store demand, within lane capacity."""
    return build_transportation_plan(db, product_id=product_id, days=days)
