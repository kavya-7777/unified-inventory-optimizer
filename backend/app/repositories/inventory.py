"""Repository: Data access layer for inventory master data."""
from typing import List, Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.models.inventory import (
    InventorySnapshot,
    Lane,
    Location,
    LocationProductPolicy,
    Product,
)


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

    def get_all_latest_snapshots(self) -> List[InventorySnapshot]:
        """Most recent snapshot per (location_id, product_id)."""
        latest = (
            self.db.query(
                InventorySnapshot.location_id,
                InventorySnapshot.product_id,
                func.max(InventorySnapshot.snapshot_date).label("max_date"),
            )
            .group_by(InventorySnapshot.location_id, InventorySnapshot.product_id)
            .subquery()
        )
        return (
            self.db.query(InventorySnapshot)
            .join(
                latest,
                (InventorySnapshot.location_id == latest.c.location_id)
                & (InventorySnapshot.product_id == latest.c.product_id)
                & (InventorySnapshot.snapshot_date == latest.c.max_date),
            )
            .all()
        )


class LaneRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self) -> List[Tuple[Lane, Location, Location]]:
        """Lanes joined with their source and target locations."""
        source = aliased(Location)
        target = aliased(Location)
        rows = (
            self.db.query(Lane, source, target)
            .join(source, Lane.source_id == source.id)
            .join(target, Lane.target_id == target.id)
            .order_by(source.type, source.name, target.name)
            .all()
        )
        return [(lane, src, tgt) for lane, src, tgt in rows]

    def get_by_id(self, lane_id: str) -> Optional[Lane]:
        return self.db.get(Lane, lane_id)


class PolicyRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return (
            self.db.query(LocationProductPolicy, Location, Product)
            .join(Location, LocationProductPolicy.location_id == Location.id)
            .join(Product, LocationProductPolicy.product_id == Product.id)
        )

    def get_all(
        self,
        q: Optional[str] = None,
        location_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tuple[LocationProductPolicy, Location, Product]]:
        query = self._base_query()
        if location_id:
            query = query.filter(LocationProductPolicy.location_id == location_id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                Location.name.ilike(like) | Product.name.ilike(like) | Product.sku.ilike(like)
            )
        rows = (
            query.order_by(Location.name, Product.name, LocationProductPolicy.id)
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [(policy, loc, prod) for policy, loc, prod in rows]

    def count(self) -> int:
        return self.db.query(LocationProductPolicy).count()

    def get_by_id_joined(
        self, policy_id: str
    ) -> Optional[Tuple[LocationProductPolicy, Location, Product]]:
        row = self._base_query().filter(LocationProductPolicy.id == policy_id).first()
        return (row[0], row[1], row[2]) if row else None

    def update(self, policy_id: str, fields: dict) -> Optional[LocationProductPolicy]:
        policy = self.db.get(LocationProductPolicy, policy_id)
        if not policy:
            return None
        for key, value in fields.items():
            setattr(policy, key, value)
        if (policy.min_s_out or 0) > (policy.max_s_out or 0):
            self.db.rollback()
            raise ValueError("min_s_out must not exceed max_s_out")
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def avg_service_level(self) -> Optional[float]:
        value = self.db.query(func.avg(LocationProductPolicy.service_level)).scalar()
        return float(value) if value is not None else None
