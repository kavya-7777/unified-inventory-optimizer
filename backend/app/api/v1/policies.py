"""API v1 router — Location-Product inventory policies."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.repositories.inventory import PolicyRepository
from app.schemas.inventory import PolicyOut, PolicyUpdate

router = APIRouter(prefix="/api/v1", tags=["policies"])


def _to_policy_out(policy, location, product) -> PolicyOut:
    return PolicyOut(
        id=policy.id,
        location_id=location.id,
        location_name=location.name,
        location_type=location.type,
        product_id=product.id,
        product_name=product.name,
        product_sku=product.sku,
        service_level=policy.service_level,
        min_s_out=policy.min_s_out,
        max_s_out=policy.max_s_out,
        holding_cost=policy.holding_cost,
        ordering_cost=policy.ordering_cost,
        review_period=policy.review_period,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/policies", response_model=List[PolicyOut])
def get_policies(
    q: Optional[str] = None,
    location_id: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List location-product policies (the GSM/inventory cost parameters that feed
    the next optimization run). `q` filters by location or product name/SKU."""
    rows = PolicyRepository(db).get_all(q=q, location_id=location_id, skip=skip, limit=limit)
    return [_to_policy_out(policy, location, product) for policy, location, product in rows]


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db)):
    repo = PolicyRepository(db)
    updated = repo.update(policy_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Policy not found")
    row = repo.get_by_id_joined(policy_id)
    policy, location, product = row
    return _to_policy_out(policy, location, product)
