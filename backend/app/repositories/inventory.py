"""Repository: Data access layer for inventory master data."""
from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session, aliased
from app.models.inventory import Location, Product, InventorySnapshot, Lane, LocationProductPolicy


class LocationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Location]:
        return self.db.query(Location).offset(skip).limit(limit).all()

    def get_by_id(self, location_id: str) -> Optional[Location]:
        return self.db.query(Location).filter(Location.id == location_id).first()

    def get_by_type(self, location_type: str) -> List[Location]:
        return self.db.query(Location).filter(Location.type == location_type).all()


class ProductRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Product]:
        return self.db.query(Product).offset(skip).limit(limit).all()

    def get_by_id(self, product_id: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

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
        """One row per (location_id, product_id): the most recent snapshot."""
        latest_dates = (
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
                latest_dates,
                (InventorySnapshot.location_id == latest_dates.c.location_id)
                & (InventorySnapshot.product_id == latest_dates.c.product_id)
                & (InventorySnapshot.snapshot_date == latest_dates.c.max_date),
            )
            .all()
        )


class LaneRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all(self):
        """Lanes joined with their source/target locations, for display."""
        Source = aliased(Location)
        Target = aliased(Location)
        return (
            self.db.query(Lane, Source, Target)
            .join(Source, Lane.source_id == Source.id)
            .join(Target, Lane.target_id == Target.id)
            .order_by(Source.type, Source.name)
            .all()
        )

    def get_by_id(self, lane_id: str) -> Optional[Lane]:
        return self.db.query(Lane).filter(Lane.id == lane_id).first()


class PolicyRepository:
    def __init__(self, db: Session):
        self.db = db

    def _base_query(self):
        return (
            self.db.query(LocationProductPolicy, Location, Product)
            .join(Location, LocationProductPolicy.location_id == Location.id)
            .join(Product, LocationProductPolicy.product_id == Product.id)
        )

    def get_all(self, q: Optional[str] = None, location_id: Optional[str] = None,
                skip: int = 0, limit: int = 100):
        query = self._base_query()
        if location_id:
            query = query.filter(LocationProductPolicy.location_id == location_id)
        if q:
            like = f"%{q}%"
            query = query.filter(
                (Location.name.ilike(like))
                | (Product.name.ilike(like))
                | (Product.sku.ilike(like))
            )
        return query.order_by(Location.name, Product.name).offset(skip).limit(limit).all()

    def count(self) -> int:
        return self.db.query(LocationProductPolicy).count()

    def get_by_id(self, policy_id: str) -> Optional[LocationProductPolicy]:
        return self.db.query(LocationProductPolicy).filter(LocationProductPolicy.id == policy_id).first()

    def get_by_id_joined(self, policy_id: str):
        return self._base_query().filter(LocationProductPolicy.id == policy_id).first()

    def update(self, policy_id: str, fields: dict) -> Optional[LocationProductPolicy]:
        policy = self.get_by_id(policy_id)
        if not policy:
            return None
        for key, value in fields.items():
            if value is not None:
                setattr(policy, key, value)
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def avg_service_level(self) -> Optional[float]:
        return self.db.query(func.avg(LocationProductPolicy.service_level)).scalar()
