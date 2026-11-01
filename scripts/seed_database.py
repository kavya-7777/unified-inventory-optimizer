"""Seed the database with the synthetic demo network. See `make seed` / `make reset-seed`."""
import argparse
import json
import os
import sys

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.session import SessionLocal  # noqa: E402
from app.demo.seed import seed  # noqa: E402

DATA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic",
                         "generated_data.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="delete all planning data (including run history) before seeding; "
                             "users are kept")
    parser.add_argument("--from-file", action="store_true",
                        help="seed from data/synthetic/generated_data.json instead of generating")
    parser.add_argument("--days", type=int, default=120, help="days of demand history")
    args = parser.parse_args()

    data = None
    if args.from_file:
        if not os.path.exists(DATA_PATH):
            sys.exit("No exported data found. Run `make generate-data` first.")
        with open(DATA_PATH) as f:
            data = json.load(f)

    with SessionLocal() as db:
        counts = seed(db, reset=args.reset, days=args.days, data=data)
    print("Database seeded: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
