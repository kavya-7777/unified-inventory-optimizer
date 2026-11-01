"""API v1 router — Location-Product inventory policies."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, require_role
from app.db.deps import get_db
from app.models.inventory import Location, LocationProductPolicy, Product
from app.repositories.inventory import PolicyRepository
from app.schemas.inventory import PolicyOut, PolicyUpdate
from app.services.users import record_event

router = APIRouter(prefix="/api/v1", tags=["policies"])


def _to_policy_out(
    policy: LocationProductPolicy, location: Location, product: Product
) -> PolicyOut:
    return PolicyOut(
        id=policy.id,
        location_id=location.id,
        location_name=location.name,
        location_type=location.type,
        product_id=product.id,
        product_name=product.name,
        product_sku=product.sku,
        service_level=policy.service_level or 0.95,
        min_s_out=policy.min_s_out or 0,
        max_s_out=policy.max_s_out if policy.max_s_out is not None else 30,
        holding_cost=policy.holding_cost or 0.0,
        ordering_cost=policy.ordering_cost or 0.0,
        review_period=policy.review_period or 1,
        processing_time=policy.processing_time or 0,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.get("/policies", response_model=List[PolicyOut])
def get_policies(
    q: Optional[str] = None,
    location_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Location-product policies. `q` filters by location name, product name or SKU."""
    rows = PolicyRepository(db).get_all(q=q, location_id=location_id, skip=skip, limit=limit)
    return [_to_policy_out(*row) for row in rows]


@router.patch("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("planner")),
):
    repo = PolicyRepository(db)
    fields = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    try:
        updated = repo.update(policy_id, fields)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    row = repo.get_by_id_joined(policy_id) if updated else None
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")
    _, location, product = row
    record_event(db, current, "policy.update", "policy", policy_id,
                 {"location": location.id, "sku": product.sku, **fields})
    return _to_policy_out(*row)
