"""Builds a lane x SKU transportation plan from the lane network and Store demand."""
from collections import defaultdict
from typing import Any, Dict, Optional, Set

from sqlalchemy.orm import Session

from app.models.inventory import LocationProductPolicy, Product
from app.repositories.demand import DemandRepository
from app.repositories.inventory import LaneRepository, ProductRepository
from app.repositories.pipeline import ForecastRepository
from app.transportation.optimizer import optimize_transportation_multi_sku


def _empty(status: str, message: Optional[str] = None, basis: Optional[str] = None):
    return {"status": status, "message": message, "lane_flows": [], "planned_units": 0.0,
            "total_cost": 0.0, "active_lanes": 0, "demand_basis": basis}


def build_transportation_plan(
    db: Session, product_id: Optional[str] = None, days: int = 28
) -> Dict[str, Any]:
    """
    Demand per store is the latest network run's forecast when one exists, otherwise the
    trailing `days` average. A SKU may only travel on lanes whose endpoints both carry it.
    """
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

    run_id = ForecastRepository(db).latest_network_run_id()
    if run_id:
        basis = "forecast"
        rows = ForecastRepository(db).mean_by_pair(run_id, product_id)
    else:
        basis = "history"
        rows = DemandRepository(db).get_avg_demand_by_location("Store", product_id, days)

    demand: Dict[str, Dict[str, float]] = {}
    for location_id, prod_id, avg_qty in rows:
        if prod_id in products and location_id in locations and avg_qty > 0:
            demand.setdefault(prod_id, {})[location_id] = avg_qty
    if not demand:
        return _empty("NO_DEMAND_DATA", "No Store demand found for the selected SKU(s).", basis)

    carriers: Dict[str, Set[str]] = defaultdict(set)
    policy_rows = db.query(LocationProductPolicy.location_id, LocationProductPolicy.product_id)
    for loc_id, prod_id in policy_rows.filter(LocationProductPolicy.product_id.in_(list(demand))):
        carriers[prod_id].add(loc_id)

    skus_demand = []
    for pid, by_loc in sorted(demand.items()):
        sku: Dict[str, Any] = {"product_id": pid, "sku": products[pid].sku,
                               "demand_by_location": by_loc}
        if carriers[pid]:
            sku["lane_ids"] = {lane["id"] for lane in lanes
                               if lane["source_id"] in carriers[pid]
                               and lane["target_id"] in carriers[pid]}
        skus_demand.append(sku)

    result = optimize_transportation_multi_sku(lanes, skus_demand)
    if result["status"] != "OPTIMAL":
        return {**_empty(result["status"], str(result.get("message") or ""), basis)}

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
    return {**result, "demand_basis": basis}
