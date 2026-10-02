import argparse
import json
import os
import random
from datetime import date, timedelta

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic", "generated_data.json")

SIZES = {
    "small": {"suppliers": 2, "dcs": 1, "stores": 5, "products": 10},
    "medium": {"suppliers": 5, "dcs": 3, "stores": 20, "products": 50},
    "large": {"suppliers": 20, "dcs": 10, "stores": 100, "products": 500},
}


def _demand_series(rng: random.Random, days: int) -> list:
    """Smooth, intermittent or lumpy daily demand, so every forecasting path is exercised."""
    kind = rng.choices(["smooth", "intermittent", "lumpy"], weights=[6, 3, 1])[0]
    base = rng.uniform(5, 60)
    series = []
    for _ in range(days):
        if kind == "smooth":
            qty = max(0.0, rng.gauss(base, base * 0.2))
        elif kind == "intermittent":
            qty = max(0.0, rng.gauss(base, base * 0.2)) if rng.random() < 0.35 else 0.0
        else:
            qty = rng.expovariate(1 / (base * 2)) if rng.random() < 0.25 else 0.0
        series.append(round(qty))
    return series


def generate_data(size: str, days: int, seed: int = 42) -> dict:
    rng = random.Random(seed)
    cfg = SIZES[size]

    suppliers = [{"id": f"SUP{i}", "name": f"Supplier {i}", "type": "Supplier"}
                 for i in range(cfg["suppliers"])]
    dcs = [{"id": f"DC{i}", "name": f"Distribution Center {i}", "type": "DC"}
           for i in range(cfg["dcs"])]
    stores = [{"id": f"ST{i}", "name": f"Store {i}", "type": "Store"}
              for i in range(cfg["stores"])]

    lanes = []
    for i, dc in enumerate(dcs):
        for sup in suppliers[i::len(dcs)] or suppliers[:1]:
            lanes.append({"source_id": sup["id"], "target_id": dc["id"],
                          "transit_time": rng.randint(3, 10),
                          "cost_per_unit": round(rng.uniform(0.5, 2.0), 2)})
    for i, store in enumerate(stores):
        dc = dcs[i % len(dcs)]
        lanes.append({"source_id": dc["id"], "target_id": store["id"],
                      "transit_time": rng.randint(1, 3),
                      "cost_per_unit": round(rng.uniform(1.0, 4.0), 2)})

    products = [{"id": f"P{i}", "name": f"Product {i}", "sku": f"SKU-{i:05d}",
                 "category": rng.choice(["General", "Grocery", "Electronics", "Apparel"]),
                 "unit_cost": round(rng.uniform(2, 200), 2)}
                for i in range(cfg["products"])]

    start = date.today() - timedelta(days=days)
    demand = [{"location_id": s["id"], "product_id": p["id"], "start_date": start.isoformat(),
               "quantities": _demand_series(rng, days)}
              for s in stores for p in products]

    return {
        "locations": suppliers + dcs + stores,
        "products": products,
        "lanes": lanes,
        "demand": demand,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", default="small", choices=list(SIZES))
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    data = generate_data(args.size, args.days, args.seed)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Generated {len(data['locations'])} locations, {len(data['products'])} products, "
          f"{len(data['lanes'])} lanes and {len(data['demand'])} demand series.")
