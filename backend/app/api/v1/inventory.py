"""API v1 router — Inventory (products, locations, inventory snapshots)."""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.repositories.inventory import LocationRepository, ProductRepository
from app.schemas.inventory import LocationOut, ProductOut

router = APIRouter(prefix="/api/v1", tags=["inventory"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/locations", response_model=List[LocationOut])
def get_locations(db: Session = Depends(get_db)):
    return LocationRepository(db).get_all()


@router.get("/products", response_model=List[ProductOut])
def get_products(db: Session = Depends(get_db)):
    return ProductRepository(db).get_all()
