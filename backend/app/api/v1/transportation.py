"""API v1 router — Transportation lane-flow plan (multi-SKU LP)."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.schemas.transportation import TransportationPlanOut
from app.services.transportation import build_transportation_plan

router = APIRouter(prefix="/api/v1", tags=["transportation"])


@router.get("/transportation/plan", response_model=TransportationPlanOut)
def get_transportation_plan(
    product_id: Optional[str] = None,
    days: int = 28,
    db: Session = Depends(get_db),
):
    """Computes lane x SKU replenishment flows that minimize freight cost, subject to
    each lane's shared capacity, using recent Store-level demand (trailing `days`)
    as each SKU's requirement. `product_id` restricts the plan to a single SKU."""
    try:
        return build_transportation_plan(db, product_id=product_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail={"code": "TRANSPORTATION_ERROR", "message": str(e)})
