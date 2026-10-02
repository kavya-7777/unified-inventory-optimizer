import json
import os
import sys
from datetime import date, timedelta

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import SessionLocal  # noqa: E402
from app.models.base import utcnow  # noqa: E402
from app.models.inventory import (  # noqa: E402
    InventorySnapshot,
    Lane,
    Location,
    LocationProductPolicy,
    Product,
)
from app.repositories.demand import DemandRepository  # noqa: E402

DATA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "synthetic", "generated_data.json"
)


def _demand_records(series: list) -> list:
    records = []
    for s in series:
        start = date.fromisoformat(s["start_date"])
        for offset, qty in enumerate(s["quantities"]):
            records.append({"location_id": s["location_id"], "product_id": s["product_id"],
                            "date": start + timedelta(days=offset), "quantity": qty})
    return records


def seed() -> None:
    if not os.path.exists(DATA_PATH):
        sys.exit("No synthetic data found. Run `make generate-data` first.")

    with open(DATA_PATH) as f:
        data = json.load(f)

    db = SessionLocal()
    try:
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
            today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            db.add_all(InventorySnapshot(**snap, snapshot_date=today)
                       for snap in data.get("inventory", []))
        db.commit()

        result = DemandRepository(db).upsert_bulk(_demand_records(data.get("demand", [])))
        print(f"Database seeded. Demand rows inserted={result['inserted_count']} "
              f"updated={result['updated_count']} ignored={result['ignored_count']}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
