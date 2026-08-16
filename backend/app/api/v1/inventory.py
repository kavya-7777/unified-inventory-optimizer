"""API v1 router — Inventory (products, locations, inventory snapshots)."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.deps import get_db
from app.repositories.inventory import LocationRepository, ProductRepository
from app.schemas.inventory import LocationOut, ProductOut

router = APIRouter(prefix="/api/v1", tags=["inventory"])


@router.get("/locations", response_model=List[LocationOut])
def get_locations(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return LocationRepository(db).get_all(skip=skip, limit=limit)


@router.get("/products", response_model=List[ProductOut])
def get_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return ProductRepository(db).get_all(skip=skip, limit=limit)
