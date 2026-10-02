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

    products = [{"id": f"P{i}", "name": f"Product {i}", "sku": f"SKU-{i:05d}",
                 "category": rng.choice(["General", "Grocery", "Electronics", "Apparel"]),
                 "unit_cost": round(rng.uniform(2, 200), 2)}
                for i in range(cfg["products"])]

    start = date.today() - timedelta(days=days)
    demand = [{"location_id": s["id"], "product_id": p["id"], "start_date": start.isoformat(),
               "quantities": _demand_series(rng, days)}
              for s in stores for p in products]

    mean = {(d["location_id"], d["product_id"]): sum(d["quantities"]) / days for d in demand}
    store_dc = {s["id"]: dcs[i % len(dcs)]["id"] for i, s in enumerate(stores)}
    store_load = {s["id"]: sum(mean[(s["id"], p["id"])] for p in products) for s in stores}
    dc_load = {dc["id"]: sum(v for st, v in store_load.items() if store_dc[st] == dc["id"])
               for dc in dcs}

    lanes = []
    for i, dc in enumerate(dcs):
        for sup in suppliers[i::len(dcs)] or suppliers[:1]:
            lanes.append({"source_id": sup["id"], "target_id": dc["id"],
                          "transit_time": rng.randint(3, 10),
                          "cost_per_unit": round(rng.uniform(0.5, 2.0), 2),
                          "capacity": round(dc_load[dc["id"]] * rng.uniform(0.8, 1.2))})
    for store in stores:
        lanes.append({"source_id": store_dc[store["id"]], "target_id": store["id"],
                      "transit_time": rng.randint(1, 3),
                      "cost_per_unit": round(rng.uniform(1.0, 4.0), 2),
                      "capacity": round(store_load[store["id"]] * rng.uniform(1.3, 1.8))})

    policies = []
    snapshots = []
    service_levels = {"Supplier": 0.90, "DC": 0.95, "Store": 0.97}
    for loc in suppliers + dcs + stores:
        for p in products:
            holding = round(p["unit_cost"] * 0.25 / 365, 4)
            policies.append({"location_id": loc["id"], "product_id": p["id"],
                             "service_level": service_levels[loc["type"]],
                             "min_s_out": 0, "max_s_out": 0 if loc["type"] == "Store" else 10,
                             "holding_cost": holding,
                             "ordering_cost": round(rng.uniform(20, 120), 2),
                             "review_period": 1 if loc["type"] == "Store" else 7})
            if loc["type"] == "Supplier":
                continue
            daily = (mean[(loc["id"], p["id"])] if loc["type"] == "Store" else
                     sum(mean[(s, p["id"])] for s, d in store_dc.items() if d == loc["id"]))
            snapshots.append({"location_id": loc["id"], "product_id": p["id"],
                              "on_hand": round(daily * rng.uniform(0.5, 6)),
                              "on_order": round(daily * rng.uniform(0, 3)),
                              "in_transit": round(daily * rng.uniform(0, 2))})

    return {
        "locations": suppliers + dcs + stores,
        "products": products,
        "lanes": lanes,
        "policies": policies,
        "inventory": snapshots,
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
          f"{len(data['lanes'])} lanes, {len(data['policies'])} policies, "
          f"{len(data['inventory'])} inventory snapshots and {len(data['demand'])} demand series.")
