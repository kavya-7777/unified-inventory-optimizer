"""API v1 router — Inventory (products, locations, lanes, inventory snapshots)."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.repositories.inventory import LocationRepository, ProductRepository, LaneRepository
from app.schemas.inventory import LocationOut, ProductOut, LaneOut

router = APIRouter(prefix="/api/v1", tags=["inventory"])


@router.get("/locations", response_model=List[LocationOut])
def get_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return LocationRepository(db).get_all(skip=skip, limit=limit)


@router.get("/products", response_model=List[ProductOut])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return ProductRepository(db).get_all(skip=skip, limit=limit)


@router.get("/lanes", response_model=List[LaneOut])
def get_lanes(db: Session = Depends(get_db)):
    rows = LaneRepository(db).get_all()
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
        for lane, source, target in rows
    ]
