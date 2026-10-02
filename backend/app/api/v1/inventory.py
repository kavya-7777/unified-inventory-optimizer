"""API v1 router — Inventory (products, locations, lanes)."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.repositories.inventory import LaneRepository, LocationRepository, ProductRepository
from app.schemas.inventory import InventoryPositionsPage, LaneOut, LocationOut, ProductOut
from app.services.inventory import STATUS_ORDER, list_positions

router = APIRouter(prefix="/api/v1", tags=["inventory"])


@router.get("/locations", response_model=List[LocationOut])
def get_locations(
    type: Optional[str] = Query(None, pattern="^(Supplier|DC|Store)$"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    repo = LocationRepository(db)
    if type:
        return repo.get_by_type(type)[skip:skip + limit]
    return repo.get_all(skip=skip, limit=limit)


@router.get("/products", response_model=List[ProductOut])
def get_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    return ProductRepository(db).get_all(skip=skip, limit=limit)


@router.get("/lanes", response_model=List[LaneOut])
def get_lanes(db: Session = Depends(get_db)):
    return [
        LaneOut(
            id=lane.id,
            source_id=source.id,
            source_name=source.name,
            source_type=source.type,
            source_region=source.region,
            target_id=target.id,
            target_name=target.name,
            target_type=target.type,
            target_region=target.region,
            transit_time=lane.transit_time,
            cost_per_unit=lane.cost_per_unit or 0.0,
            capacity=lane.capacity,
            created_at=lane.created_at,
        )
        for lane, source, target in LaneRepository(db).get_all()
    ]


@router.get("/inventory/positions", response_model=InventoryPositionsPage)
def get_inventory_positions(
    location_type: Optional[str] = Query(None, pattern="^(Supplier|DC|Store)$"),
    location_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = Query(None, pattern="^(" + "|".join(STATUS_ORDER) + ")$"),
    q: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Latest stock per location x SKU against the most recent optimized targets."""
    return list_positions(db, location_type, location_id, product_id, status, q, skip, limit)
