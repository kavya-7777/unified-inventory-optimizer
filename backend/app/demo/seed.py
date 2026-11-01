"""Loads the synthetic demo network (see generate.py) into the database."""
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.demo.generate import generate_data
from app.models.inventory import (
    Alert,
    DemandForecast,
    DemandHistory,
    InventorySnapshot,
    Lane,
    LeadTimeObservation,
    Location,
    LocationProductPolicy,
    OptimizationResult,
    PipelineRun,
    Product,
)
from app.repositories.demand import DemandRepository

# Children before parents, so foreign keys never block the delete. Users, the activity
# log and the import history are kept.
RESET_ORDER = [
    Alert, DemandForecast, OptimizationResult, PipelineRun, InventorySnapshot,
    DemandHistory, LeadTimeObservation, LocationProductPolicy, Lane, Product, Location,
]


def _demand_records(series: list) -> list:
    records = []
    for s in series:
        start = date.fromisoformat(s["start_date"])
        for offset, qty in enumerate(s["quantities"]):
            records.append({"location_id": s["location_id"], "product_id": s["product_id"],
                            "date": start + timedelta(days=offset), "quantity": qty})
    return records


def reset_data(db: Session) -> None:
    for model in RESET_ORDER:
        db.query(model).delete(synchronize_session=False)
    db.commit()


def seed(db: Session, reset: bool = False, days: int = 120,
         data: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    """
    Adds the demo network, keeping existing rows (or wiping all planning data first when
    `reset`). Demand history is generated to end yesterday, so forecasts look current.
    """
    data = data or generate_data(days=days, end=date.today())
    try:
        if reset:
            reset_data(db)

        known_locs = {x for (x,) in db.query(Location.id)}
        db.add_all(Location(**loc) for loc in data.get("locations", [])
                   if loc["id"] not in known_locs)

        known_prods = {x for (x,) in db.query(Product.id)}
        db.add_all(Product(**p) for p in data.get("products", []) if p["id"] not in known_prods)
        # No ORM relationships between these models, so the unit of work won't order
        # inserts by foreign key; flush parents before adding rows that reference them.
        db.flush()

        known_lanes = set(db.query(Lane.source_id, Lane.target_id).all())
        db.add_all(Lane(**lane) for lane in data.get("lanes", [])
                   if (lane["source_id"], lane["target_id"]) not in known_lanes)

        known_policies = set(db.query(LocationProductPolicy.location_id,
                                      LocationProductPolicy.product_id).all())
        db.add_all(LocationProductPolicy(**pol) for pol in data.get("policies", [])
                   if (pol["location_id"], pol["product_id"]) not in known_policies)

        if not db.query(InventorySnapshot.id).first():
            today = datetime.combine(date.today(), time.min)
            db.add_all(InventorySnapshot(**snap, snapshot_date=today)
                       for snap in data.get("inventory", []))
        db.commit()

        result = DemandRepository(db).upsert_bulk(_demand_records(data.get("demand", [])))
    except Exception:
        db.rollback()
        raise
    return {
        "locations": len(data.get("locations", [])),
        "products": len(data.get("products", [])),
        "lanes": len(data.get("lanes", [])),
        "policies": len(data.get("policies", [])),
        "demand_rows": result["inserted_count"] + result["updated_count"],
    }
