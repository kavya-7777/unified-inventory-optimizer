"""Service layer: builds a transportation plan (lane x SKU flows) from the current
lane network and recent Store-level demand, via the multi-commodity LP."""
from typing import Optional
from sqlalchemy.orm import Session
from app.repositories.inventory import LaneRepository, ProductRepository
from app.repositories.demand import DemandRepository
from app.transportation.optimizer import optimize_transportation_multi_sku


def build_transportation_plan(db: Session, product_id: Optional[str] = None, days: int = 28) -> dict:
    lane_rows = LaneRepository(db).get_all()
    if not lane_rows:
        return {"status": "NO_EDGES", "lane_flows": [], "planned_units": 0.0, "total_cost": 0.0, "active_lanes": 0}

    lanes = []
    location_lookup = {}
    for lane, source, target in lane_rows:
        lanes.append({
            "id": lane.id,
            "source_id": lane.source_id,
            "target_id": lane.target_id,
            "cost_per_unit": lane.cost_per_unit or 0.0,
            "capacity": lane.capacity,
            "transit_time": lane.transit_time,
        })
        location_lookup[source.id] = source
        location_lookup[target.id] = target

    products = ProductRepository(db).get_all(skip=0, limit=100_000)
    if product_id:
        products = [p for p in products if p.id == product_id]
    product_lookup = {p.id: p for p in products}

    demand_rows = DemandRepository(db).get_avg_demand_by_location(
        location_type="Store", product_id=product_id, days=days
    )
    demand_by_product: dict[str, dict[str, float]] = {}
    for location_id, prod_id, avg_qty in demand_rows:
        if prod_id not in product_lookup:
            continue
        demand_by_product.setdefault(prod_id, {})[location_id] = float(avg_qty or 0.0)

    if not demand_by_product:
        return {
            "status": "NO_DEMAND_DATA",
            "message": "No recent Store-level demand history found for the selected SKU(s).",
            "lane_flows": [], "planned_units": 0.0, "total_cost": 0.0, "active_lanes": 0,
        }

    skus_demand = [
        {"product_id": pid, "sku": product_lookup[pid].sku, "demand_by_location": demand_by_product[pid]}
        for pid in demand_by_product
    ]

    result = optimize_transportation_multi_sku(lanes, skus_demand)
    if result["status"] != "OPTIMAL":
        return result

    enriched_flows = []
    for flow in result["lane_flows"]:
        source = location_lookup[flow["source_id"]]
        target = location_lookup[flow["target_id"]]
        product = product_lookup[flow["product_id"]]
        enriched_flows.append({
            **flow,
            "source_name": source.name,
            "source_type": source.type,
            "target_name": target.name,
            "target_type": target.type,
            "product_name": product.name,
        })
    result["lane_flows"] = enriched_flows
    return result
