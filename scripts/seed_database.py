import argparse
import json
import os
import sys
from datetime import date, datetime, time, timedelta

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from generate_data import generate_data  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.models.inventory import (  # noqa: E402
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


# Children before parents, so foreign keys never block the delete.
RESET_ORDER = [
    Alert, DemandForecast, OptimizationResult, PipelineRun, InventorySnapshot,
    DemandHistory, LeadTimeObservation, LocationProductPolicy, Lane, Product, Location,
]


def load_data(from_file: bool, days: int) -> dict:
    """
    By default the dataset is generated fresh (fixed random seed) so demand history always
    ends yesterday; `from_file` loads the exported JSON exactly as written.
    """
    if not from_file:
        return generate_data(days=days, end=date.today())
    if not os.path.exists(DATA_PATH):
        sys.exit("No exported data found. Run `make generate-data` first.")
    with open(DATA_PATH) as f:
        return json.load(f)


def seed(reset: bool = False, from_file: bool = False, days: int = 120) -> None:
    data = load_data(from_file, days)

    db = SessionLocal()
    try:
        if reset:
            for model in RESET_ORDER:
                db.query(model).delete(synchronize_session=False)
            db.commit()
            print("Existing data removed.")

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
        print(f"Database seeded. Demand rows inserted={result['inserted_count']} "
              f"updated={result['updated_count']} ignored={result['ignored_count']}.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="delete all existing data (including run history) before seeding")
    parser.add_argument("--from-file", action="store_true",
                        help="seed from data/synthetic/generated_data.json instead of generating")
    parser.add_argument("--days", type=int, default=120, help="days of demand history")
    args = parser.parse_args()
    seed(reset=args.reset, from_file=args.from_file, days=args.days)
