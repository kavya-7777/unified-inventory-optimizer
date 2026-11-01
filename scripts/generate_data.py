"""Export the synthetic demo dataset to data/synthetic/generated_data.json."""
import argparse
import json
import os
import sys

if os.path.exists("/app/app"):
    sys.path.insert(0, "/app")
else:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.demo.generate import generate_data  # noqa: E402

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic", "generated_data.json")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data = generate_data(args.days, args.seed)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Generated {len(data['locations'])} locations, {len(data['products'])} products, "
          f"{len(data['lanes'])} lanes, {len(data['policies'])} policies, "
          f"{len(data['inventory'])} inventory snapshots and {len(data['demand'])} demand series.")
