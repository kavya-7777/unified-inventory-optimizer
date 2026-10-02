"""Repository: Data access layer for inventory master data."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.inventory import InventorySnapshot, Location, Product


class LocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Location]:
        return self.db.query(Location).order_by(Location.id).offset(skip).limit(limit).all()

    def get_by_id(self, location_id: str) -> Optional[Location]:
        return self.db.get(Location, location_id)

    def get_by_type(self, location_type: str) -> List[Location]:
        return (
            self.db.query(Location)
            .filter(Location.type == location_type)
            .order_by(Location.id)
            .all()
        )


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.db.query(Product).order_by(Product.id).offset(skip).limit(limit).all()

    def get_by_id(self, product_id: str) -> Optional[Product]:
        return self.db.get(Product, product_id)

    def get_by_sku(self, sku: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.sku == sku).first()


class InventoryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_snapshot(self, location_id: str, product_id: str) -> Optional[InventorySnapshot]:
        return (
            self.db.query(InventorySnapshot)
            .filter(
                InventorySnapshot.location_id == location_id,
                InventorySnapshot.product_id == product_id,
            )
            .order_by(InventorySnapshot.snapshot_date.desc())
            .first()
        )
