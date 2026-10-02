import json
import os
import sys
from datetime import date, timedelta

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import SessionLocal  # noqa: E402
from app.models.inventory import Lane, Location, Product  # noqa: E402
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

        known_lanes = set(db.query(Lane.source_id, Lane.target_id).all())
        db.add_all(Lane(**lane) for lane in data.get("lanes", [])
                   if (lane["source_id"], lane["target_id"]) not in known_lanes)
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
