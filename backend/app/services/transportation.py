"""Builds a lane x SKU transportation plan from the lane network and recent Store demand."""
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.inventory import Product
from app.repositories.demand import DemandRepository
from app.repositories.inventory import LaneRepository, ProductRepository
from app.transportation.optimizer import optimize_transportation_multi_sku


def _empty(status: str, message: Optional[str] = None) -> Dict[str, Any]:
    return {"status": status, "message": message, "lane_flows": [], "planned_units": 0.0,
            "total_cost": 0.0, "active_lanes": 0}


def build_transportation_plan(
    db: Session, product_id: Optional[str] = None, days: int = 28
) -> Dict[str, Any]:
    lane_rows = LaneRepository(db).get_all()
    if not lane_rows:
        return _empty("NO_EDGES", "No lanes configured.")

    lanes = []
    locations = {}
    for lane, source, target in lane_rows:
        lanes.append({
            "id": lane.id,
            "source_id": lane.source_id,
            "target_id": lane.target_id,
            "cost_per_unit": lane.cost_per_unit or 0.0,
            "capacity": lane.capacity,
            "transit_time": lane.transit_time,
        })
        locations[source.id] = source
        locations[target.id] = target

    if product_id:
        product = ProductRepository(db).get_by_id(product_id)
        products: Dict[str, Product] = {product.id: product} if product else {}
    else:
        products = {p.id: p for p in db.query(Product).all()}

    demand: Dict[str, Dict[str, float]] = {}
    rows = DemandRepository(db).get_avg_demand_by_location("Store", product_id, days)
    for location_id, prod_id, avg_qty in rows:
        if prod_id in products and location_id in locations and avg_qty > 0:
            demand.setdefault(prod_id, {})[location_id] = avg_qty

    if not demand:
        return _empty("NO_DEMAND_DATA", "No recent Store demand found for the selected SKU(s).")

    skus_demand = [
        {"product_id": pid, "sku": products[pid].sku, "demand_by_location": by_loc}
        for pid, by_loc in sorted(demand.items())
    ]
    result = optimize_transportation_multi_sku(lanes, skus_demand)
    if result["status"] != "OPTIMAL":
        return {**_empty(result["status"]), "message": str(result.get("message") or "")}

    for flow in result["lane_flows"]:
        source = locations[flow["source_id"]]
        target = locations[flow["target_id"]]
        flow.update({
            "source_name": source.name,
            "source_type": source.type,
            "target_name": target.name,
            "target_type": target.type,
            "product_name": products[flow["product_id"]].name,
        })
    return result
