"""
Synthetic South-India retail network: 5 suppliers → 3 regional DCs → 20 stores, 50 SKUs.

A location carries a product iff it has a policy for it; suppliers only get policies for
the categories they make, which is how the optimizer knows who sources what.
"""
import argparse
import json
import math
import os
import random
from datetime import date, timedelta

OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic", "generated_data.json")

SUPPLIERS = [
    ("SUP-MYS", "Mysuru Food Processing Unit", "Karnataka", ["Grocery"]),
    ("SUP-VJA", "Vijayawada Agro Foods", "Andhra Pradesh", ["Grocery"]),
    ("SUP-HSR", "Hosur Consumer Goods Plant", "Tamil Nadu", ["Personal Care", "Home Care"]),
    ("SUP-SRP", "Sriperumbudur Electronics Plant", "Tamil Nadu", ["Electronics"]),
    ("SUP-TPR", "Tiruppur Garment Unit", "Tamil Nadu", ["Apparel"]),
]

DCS = [
    ("DC-CHN", "Chennai Regional DC", "Tamil Nadu"),
    ("DC-BLR", "Bengaluru Regional DC", "Karnataka"),
    ("DC-HYD", "Hyderabad Regional DC", "Telangana"),
]

# (id, name, region, serving DC, size factor)
STORES = [
    ("ST-CHN-TNAGAR", "T. Nagar Store, Chennai", "Tamil Nadu", "DC-CHN", 1.4),
    ("ST-CHN-ANNANAGAR", "Anna Nagar Store, Chennai", "Tamil Nadu", "DC-CHN", 1.2),
    ("ST-CHN-VELACHERY", "Velachery Store, Chennai", "Tamil Nadu", "DC-CHN", 1.1),
    ("ST-CHN-ADYAR", "Adyar Store, Chennai", "Tamil Nadu", "DC-CHN", 0.9),
    ("ST-CHN-TAMBARAM", "Tambaram Store, Chennai", "Tamil Nadu", "DC-CHN", 0.8),
    ("ST-CBE-RSPURAM", "R.S. Puram Store, Coimbatore", "Tamil Nadu", "DC-CHN", 0.9),
    ("ST-MDU-KKNAGAR", "K.K. Nagar Store, Madurai", "Tamil Nadu", "DC-CHN", 0.7),
    ("ST-BLR-INDIRANAGAR", "Indiranagar Store, Bengaluru", "Karnataka", "DC-BLR", 1.3),
    ("ST-BLR-KORAMANGALA", "Koramangala Store, Bengaluru", "Karnataka", "DC-BLR", 1.3),
    ("ST-BLR-JAYANAGAR", "Jayanagar Store, Bengaluru", "Karnataka", "DC-BLR", 1.0),
    ("ST-BLR-WHITEFIELD", "Whitefield Store, Bengaluru", "Karnataka", "DC-BLR", 1.1),
    ("ST-BLR-MALLESHWARAM", "Malleshwaram Store, Bengaluru", "Karnataka", "DC-BLR", 0.8),
    ("ST-MYS-VIJAYANAGAR", "Vijayanagar Store, Mysuru", "Karnataka", "DC-BLR", 0.7),
    ("ST-MLR-HAMPANKATTA", "Hampankatta Store, Mangaluru", "Karnataka", "DC-BLR", 0.6),
    ("ST-HYD-BANJARAHILLS", "Banjara Hills Store, Hyderabad", "Telangana", "DC-HYD", 1.3),
    ("ST-HYD-GACHIBOWLI", "Gachibowli Store, Hyderabad", "Telangana", "DC-HYD", 1.2),
    ("ST-HYD-KUKATPALLY", "Kukatpally Store, Hyderabad", "Telangana", "DC-HYD", 1.0),
    ("ST-HYD-SECUNDERABAD", "Secunderabad Store, Hyderabad", "Telangana", "DC-HYD", 0.9),
    ("ST-WGL-HANAMKONDA", "Hanamkonda Store, Warangal", "Telangana", "DC-HYD", 0.6),
    ("ST-VSP-DWARAKANAGAR", "Dwaraka Nagar Store, Visakhapatnam", "Andhra Pradesh", "DC-HYD", 0.8),
]

# Supplier → DC transit days
SUPPLY_TRANSIT = {
    "SUP-MYS": {"DC-CHN": 3, "DC-BLR": 1, "DC-HYD": 4},
    "SUP-VJA": {"DC-CHN": 3, "DC-BLR": 4, "DC-HYD": 2},
    "SUP-HSR": {"DC-CHN": 2, "DC-BLR": 1, "DC-HYD": 4},
    "SUP-SRP": {"DC-CHN": 1, "DC-BLR": 2, "DC-HYD": 4},
    "SUP-TPR": {"DC-CHN": 3, "DC-BLR": 2, "DC-HYD": 5},
}

# category: (sku prefix, demand style, store service level, [(name, unit cost ₹, base units/day)])
CATALOG = {
    "Grocery": ("GRO", "weekly", 0.98, [
        ("Sona Masoori Rice 5 kg", 320, 14), ("Basmati Rice 1 kg", 140, 9),
        ("Toor Dal 1 kg", 155, 11), ("Moong Dal 500 g", 75, 6),
        ("Atta Whole Wheat 5 kg", 245, 10), ("Sunflower Oil 1 L", 150, 13),
        ("Groundnut Oil 1 L", 190, 7), ("Sugar 1 kg", 46, 12),
        ("Iodised Salt 1 kg", 22, 9), ("Filter Coffee Powder 500 g", 260, 5),
        ("Tea Dust 500 g", 230, 6), ("Rava 1 kg", 58, 5),
        ("Poha 500 g", 42, 4), ("Tamarind 500 g", 95, 3),
        ("Sambar Powder 200 g", 70, 6), ("Instant Noodles 4-Pack", 56, 15),
    ]),
    "Personal Care": ("PER", "weekly", 0.97, [
        ("Herbal Shampoo 340 ml", 210, 4), ("Coconut Hair Oil 500 ml", 185, 6),
        ("Neem Soap 4-Pack", 120, 8), ("Toothpaste 150 g", 95, 9),
        ("Toothbrush Soft 3-Pack", 99, 4), ("Talcum Powder 300 g", 160, 3),
        ("Face Wash 100 ml", 150, 3), ("Hand Wash Refill 750 ml", 110, 4),
        ("Shaving Cream 70 g", 65, 2), ("Sanitary Pads Pack of 20", 180, 5),
    ]),
    "Home Care": ("HOM", "weekly", 0.96, [
        ("Detergent Powder 1 kg", 120, 9), ("Dishwash Bar 500 g", 40, 8),
        ("Dishwash Liquid 750 ml", 140, 4), ("Floor Cleaner 1 L", 175, 4),
        ("Toilet Cleaner 500 ml", 95, 3), ("Garbage Bags Medium", 85, 3),
        ("Mosquito Repellent Refill", 80, 5), ("Agarbatti 100 Sticks", 60, 6),
    ]),
    "Electronics": ("ELE", "intermittent", 0.95, [
        ("LED Bulb 9 W", 110, 3.0), ("LED Batten 20 W", 420, 0.6),
        ("USB-C Charger 20 W", 650, 0.5), ("Extension Board 4-Socket", 480, 0.4),
        ("AA Batteries 4-Pack", 140, 2.0), ("Wired Earphones", 350, 0.5),
        ("Ceiling Fan Regulator", 290, 0.25), ("Table Fan 400 mm", 1850, 0.15),
    ]),
    "Apparel": ("APP", "erratic", 0.95, [
        ("Cotton Veshti", 450, 1.2), ("Cotton Saree", 1250, 0.6),
        ("Men's Cotton Shirt", 799, 1.0), ("Kids T-Shirt", 299, 1.5),
        ("Cotton Towel", 220, 1.8), ("Bedsheet Double", 699, 0.5),
        ("Innerwear 3-Pack", 399, 2.0), ("Socks 3-Pair", 199, 1.4),
    ]),
}

WEEKLY = [0.9, 0.85, 0.9, 0.95, 1.05, 1.3, 1.25]  # Mon..Sun multipliers


def _demand_series(rng: random.Random, style: str, base: float, start: date, days: int) -> list:
    trend = rng.uniform(-0.002, 0.004)
    series = []
    for t in range(days):
        dow = WEEKLY[(start + timedelta(days=t)).weekday()]
        level = base * (1 + trend * t)
        if style == "weekly":
            qty = rng.gauss(level * dow, level * 0.18)
        elif style == "erratic":
            qty = rng.gauss(level * dow, level * 0.6) if rng.random() < 0.85 else 0.0
            if rng.random() < 0.04:
                qty += level * rng.uniform(3, 6)        # festival / promotion spike
        else:
            p = min(0.9, 1 - math.exp(-level))          # chance of any sale that day
            qty = rng.expovariate(1 / max(1.0, level / p)) if rng.random() < p else 0.0
        series.append(max(0, round(qty)))
    return series


def generate_data(days: int, seed: int = 42, end: date | None = None) -> dict:
    rng = random.Random(seed)
    end = end or date.today()
    start = end - timedelta(days=days)

    locations = (
        [{"id": i, "name": n, "type": "Supplier", "region": r} for i, n, r, _ in SUPPLIERS]
        + [{"id": i, "name": n, "type": "DC", "region": r} for i, n, r in DCS]
        + [{"id": i, "name": n, "type": "Store", "region": r} for i, n, r, _, _ in STORES]
    )

    products, product_meta = [], {}
    for category, (prefix, style, store_sl, items) in CATALOG.items():
        for idx, (name, cost, base) in enumerate(items, start=1):
            sku = f"{prefix}-{idx:03d}"
            products.append({"id": sku, "name": name, "sku": sku, "category": category,
                             "unit_cost": float(cost)})
            product_meta[sku] = (category, style, store_sl, base, float(cost))

    demand, mean = [], {}
    for store_id, _, _, _, size in STORES:
        for sku, (_, style, _, base, _) in product_meta.items():
            qty = _demand_series(rng, style, base * size * rng.uniform(0.8, 1.2), start, days)
            demand.append({"location_id": store_id, "product_id": sku,
                           "start_date": start.isoformat(), "quantities": qty})
            mean[(store_id, sku)] = sum(qty) / days

    store_dc = {s[0]: s[3] for s in STORES}
    dc_mean = {(dc, sku): sum(mean[(st, sku)] for st, d in store_dc.items() if d == dc)
               for dc, _, _ in DCS for sku in product_meta}
    sources = {cat: [s[0] for s in SUPPLIERS if cat in s[3]] for cat in CATALOG}

    lanes = []
    for sup_id, _, _, cats in SUPPLIERS:
        for dc_id, _, _ in DCS:
            flow = sum(dc_mean[(dc_id, sku)] / len(sources[meta[0]])
                       for sku, meta in product_meta.items() if meta[0] in cats)
            transit = SUPPLY_TRANSIT[sup_id][dc_id]
            lanes.append({"source_id": sup_id, "target_id": dc_id, "transit_time": transit,
                          "cost_per_unit": round(1.5 + 1.2 * transit + rng.uniform(0, 1), 2),
                          "capacity": round(flow * rng.uniform(1.6, 2.2))})
    for store_id, _, _, dc_id, _ in STORES:
        flow = sum(mean[(store_id, sku)] for sku in product_meta)
        transit = 1 if store_id.split("-")[1] == dc_id.split("-")[1] else 2
        lanes.append({"source_id": dc_id, "target_id": store_id, "transit_time": transit,
                      "cost_per_unit": round(rng.uniform(2.0, 4.5) * transit, 2),
                      "capacity": round(flow * rng.uniform(1.4, 1.8))})

    policies, snapshots = [], []
    for loc in locations:
        for sku, (category, _, store_sl, _, cost) in product_meta.items():
            if loc["type"] == "Supplier" and loc["id"] not in sources[category]:
                continue
            kind = loc["type"]
            policies.append({
                "location_id": loc["id"],
                "product_id": sku,
                "service_level": {"Supplier": 0.90, "DC": 0.95, "Store": store_sl}[kind],
                "min_s_out": 0,
                "max_s_out": {"Supplier": 14, "DC": 7, "Store": 0}[kind],
                "holding_cost": round(cost * 0.25 / 365, 4),
                "ordering_cost": {"Supplier": 2500.0, "DC": 1200.0, "Store": 400.0}[kind],
                "review_period": {"Supplier": 7, "DC": 3, "Store": 1}[kind],
                "processing_time": {"Supplier": 3, "DC": 1, "Store": 0}[kind],
            })
            if kind == "Supplier":
                continue
            daily = mean[(loc["id"], sku)] if kind == "Store" else dc_mean[(loc["id"], sku)]
            cover = rng.uniform(4, 16) if kind == "DC" else rng.uniform(0.5, 9)
            snapshots.append({"location_id": loc["id"], "product_id": sku,
                              "on_hand": round(daily * cover),
                              "on_order": round(daily * rng.uniform(0, 4)),
                              "in_transit": round(daily * rng.uniform(0, 2))})

    return {
        "locations": locations,
        "products": products,
        "lanes": lanes,
        "policies": policies,
        "inventory": snapshots,
        "demand": demand,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--size", help="ignored; kept for Makefile compatibility")
    args = parser.parse_args()

    data = generate_data(args.days, args.seed)
    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"Generated {len(data['locations'])} locations, {len(data['products'])} products, "
          f"{len(data['lanes'])} lanes, {len(data['policies'])} policies, "
          f"{len(data['inventory'])} inventory snapshots and {len(data['demand'])} demand series.")
