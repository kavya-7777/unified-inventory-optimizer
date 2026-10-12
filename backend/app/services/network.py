"""
Database-driven unified optimization pipeline.

1. Forecast every store x SKU demand series (automatic model selection).
2. Roll forecast demand up the network to DCs and suppliers.
3. Solve the guaranteed-service model per SKU and persist stock targets.
4. Compare targets with current stock and raise stockout-risk alerts.
5. Plan lane flows for the forecast demand with the multi-SKU transportation LP.
"""
import logging
import math
import statistics
import time
from collections import Counter, defaultdict
from datetime import timedelta
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from app.forecasting.engine import forecast_series
from app.models.inventory import Lane, Location, LocationProductPolicy, Product
from app.optimization.errors import NetworkValidationError
from app.optimization.runner import run_optimization_pipeline
from app.repositories.demand import DemandRepository
from app.repositories.inventory import InventoryRepository
from app.repositories.pipeline import (
    AlertRepository,
    ForecastRepository,
    OptimizationResultRepository,
    PipelineRunRepository,
)
from app.transportation.optimizer import optimize_transportation_multi_sku

log = logging.getLogger(__name__)

Pair = Tuple[str, str]


class NetworkData:
    """Snapshot of master data needed to build per-SKU networks."""

    def __init__(self, db: Session, product_ids: Optional[List[str]]):
        query = db.query(Product)
        if product_ids:
            query = query.filter(Product.id.in_(product_ids))
        self.products: Dict[str, Product] = {p.id: p for p in query.order_by(Product.id)}
        self.locations: Dict[str, Location] = {loc.id: loc for loc in db.query(Location)}
        self.lanes: List[Lane] = db.query(Lane).all()
        self.policies: Dict[Pair, LocationProductPolicy] = {
            (p.location_id, p.product_id): p
            for p in db.query(LocationProductPolicy).filter(
                LocationProductPolicy.product_id.in_(list(self.products))
            )
        }

    def carriers(self, product_id: str) -> Set[str]:
        """Locations that stock or supply the product (they have a policy for it)."""
        return {loc for (loc, prod) in self.policies if prod == product_id}

    def lanes_for(self, product_id: str) -> List[Lane]:
        nodes = self.carriers(product_id)
        return [lane for lane in self.lanes if lane.source_id in nodes and lane.target_id in nodes]


def echelon_demand(
    nodes: Set[str], lanes: List[Lane], store_demand: Dict[str, Tuple[float, float]]
) -> Dict[str, Tuple[float, float]]:
    """
    Demand seen at each node: its own (store) demand plus the share it supplies to each
    downstream node. A node with k suppliers splits its demand equally between them; with
    independent demands, means add and variances add (scaled by the share squared).
    """
    preds: Dict[str, List[str]] = defaultdict(list)
    succs: Dict[str, List[str]] = defaultdict(list)
    for lane in lanes:
        preds[lane.target_id].append(lane.source_id)
        succs[lane.source_id].append(lane.target_id)

    result: Dict[str, Tuple[float, float]] = {}

    def visit(node: str) -> Tuple[float, float]:
        if node in result:
            return result[node]
        mean, std = store_demand.get(node, (0.0, 0.0))
        var = std ** 2
        for child in succs[node]:
            share = 1 / len(preds[child])
            child_mean, child_std = visit(child)
            mean += share * child_mean
            var += (share * child_std) ** 2
        result[node] = (mean, math.sqrt(var))
        return result[node]

    for node in nodes:
        visit(node)
    return result


def _gsm_nodes(
    data: NetworkData, product_id: str, nodes: Set[str], demand: Dict[str, Tuple[float, float]]
) -> List[Dict[str, Any]]:
    out = []
    for loc_id in sorted(nodes):
        policy = data.policies[(loc_id, product_id)]
        mean, std = demand.get(loc_id, (0.0, 0.0))
        out.append({
            "id": loc_id,
            "type": data.locations[loc_id].type,
            "processing_time": policy.processing_time or 0,
            "demand_mean": mean,
            "demand_std": std,
            "holding_cost": policy.holding_cost or 0.0,
            "ordering_cost": policy.ordering_cost or 0.0,
            "max_s_out": policy.max_s_out if policy.max_s_out is not None else 30,
            "min_s_out": policy.min_s_out or 0,
            "service_level": policy.service_level or 0.95,
            "location_id": loc_id,
            "product_id": product_id,
        })
    return out


def _stockout_alerts(
    db: Session, run_id: str, data: NetworkData, results: Dict[Pair, Dict[str, Any]]
) -> int:
    alert_repo = AlertRepository(db)
    alert_repo.resolve_open("STOCKOUT_RISK", list(data.products))
    count = 0
    for snap in InventoryRepository(db).get_all_latest_snapshots():
        key = (snap.location_id, snap.product_id)
        result = results.get(key)
        if not result or result["safety_stock"] <= 0:
            continue
        on_hand = snap.on_hand or 0.0
        ss = result["safety_stock"]
        if on_hand >= ss:
            continue
        loc = data.locations[snap.location_id]
        prod = data.products[snap.product_id]
        alert_repo.create(
            alert_type="STOCKOUT_RISK",
            severity="CRITICAL" if on_hand < 0.5 * ss else "WARNING",
            message=(f"{loc.name} · {prod.name}: on hand {on_hand:,.0f} is below "
                     f"safety stock {ss:,.0f}"),
            pipeline_run_id=run_id,
            location_id=snap.location_id,
            product_id=snap.product_id,
        )
        count += 1
    return count


def _transportation(
    db: Session, run_id: str, data: NetworkData, store_demand: Dict[Pair, float]
) -> Dict[str, Any]:
    lanes = [{"id": lane.id, "source_id": lane.source_id, "target_id": lane.target_id,
              "cost_per_unit": lane.cost_per_unit or 0.0, "capacity": lane.capacity,
              "transit_time": lane.transit_time} for lane in data.lanes]
    by_product: Dict[str, Dict[str, float]] = defaultdict(dict)
    for (loc, prod), qty in store_demand.items():
        if qty > 0:
            by_product[prod][loc] = qty
    skus = [
        {"product_id": pid, "sku": data.products[pid].sku, "demand_by_location": demand,
         "lane_ids": {lane.id for lane in data.lanes_for(pid)}}
        for pid, demand in sorted(by_product.items())
    ]
    if not skus:
        return {"status": "NO_DEMAND_DATA"}
    plan = optimize_transportation_multi_sku(lanes, skus)
    if plan["status"] == "INFEASIBLE":
        AlertRepository(db).create(
            alert_type="TRANSPORT_INFEASIBLE",
            severity="CRITICAL",
            message=f"Lane capacity cannot cover forecast demand: {plan.get('message')}",
            pipeline_run_id=run_id,
        )
    return {k: plan.get(k) for k in
            ("status", "total_cost", "planned_units", "capacity_utilization", "active_lanes")}


def run_network_pipeline(db: Session, run_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    started = time.perf_counter()
    horizon = params.get("horizon", 14)
    history_days = params.get("history_days", 90)

    data = NetworkData(db, params.get("product_ids"))
    if not data.products:
        raise NetworkValidationError(["No products found for this run."])

    demand_repo = DemandRepository(db)
    end = demand_repo.latest_date()
    if end is None:
        raise NetworkValidationError(["No demand history available — seed or ingest demand."])

    # 1. Forecast every store series that has a policy.
    stores = [loc_id for loc_id, loc in data.locations.items() if loc.type == "Store"]
    _, series = demand_repo.get_daily_series(history_days, list(data.products), stores, end)
    forecasts: Dict[Pair, Dict[str, Any]] = {}
    forecast_rows = []
    for (loc_id, prod_id), policy in data.policies.items():
        if data.locations[loc_id].type != "Store":
            continue
        result = forecast_series(series.get((loc_id, prod_id), [0.0] * history_days), horizon)
        forecasts[(loc_id, prod_id)] = result
        for k in range(horizon):
            forecast_rows.append({
                "pipeline_run_id": run_id,
                "location_id": loc_id,
                "product_id": prod_id,
                "forecast_date": end + timedelta(days=k + 1),
                "quantity": result["forecast"][k],
                "lower_bound": result["lower"][k],
                "upper_bound": result["upper"][k],
                "method": result["method"],
                "pattern": result["pattern"],
            })
    ForecastRepository(db).bulk_save_rows(forecast_rows)

    # 2-3. Per-SKU guaranteed-service optimization.
    results: Dict[Pair, Dict[str, Any]] = {}
    failures, fallbacks = [], []
    result_repo = OptimizationResultRepository(db)
    for prod_id in data.products:
        nodes = data.carriers(prod_id)
        lanes = data.lanes_for(prod_id)
        store_demand = {loc: (f["demand_mean"], f["demand_std"])
                        for (loc, p), f in forecasts.items() if p == prod_id}
        demand = echelon_demand(nodes, lanes, store_demand)
        gsm_nodes = _gsm_nodes(data, prod_id, nodes, demand)
        edges = [{"source": lane.source_id, "target": lane.target_id,
                  "transit_time": lane.transit_time} for lane in lanes]
        try:
            outcome = run_optimization_pipeline({
                "pipeline_run_id": run_id,
                "nodes": gsm_nodes,
                "edges": edges,
                "max_service_time": params.get("max_service_time", 30),
            })
        except NetworkValidationError as e:
            failures.append({"product_id": prod_id, "errors": e.errors})
            continue
        if outcome["fallback_used"]:
            fallbacks.append(prod_id)
        node_info = {n["id"]: n for n in gsm_nodes}
        for node_id, r in outcome["node_results"].items():
            info = node_info[node_id]
            r.update(demand_mean=round(info["demand_mean"], 4),
                     demand_std=round(info["demand_std"], 4),
                     service_level=info["service_level"])
            results[(node_id, prod_id)] = r
        result_repo.bulk_save(run_id, outcome["node_results"])

    if fallbacks:
        AlertRepository(db).create(
            alert_type="SOLVER_FALLBACK",
            severity="INFO",
            message=f"Heuristic fallback used for {len(fallbacks)} SKU(s): "
                    + ", ".join(fallbacks[:10]),
            pipeline_run_id=run_id,
        )

    # 4. Stock health against the new targets.
    stockout_alerts = _stockout_alerts(db, run_id, data, results)

    # 5. Lane flows for the forecast demand.
    transport = _transportation(
        db, run_id, data, {k: f["demand_mean"] for k, f in forecasts.items()}
    )

    mases = [f["metrics"]["mase"] for f in forecasts.values()
             if f["metrics"] and f["metrics"].get("mase") is not None]
    unit_cost = {pid: p.unit_cost or 0.0 for pid, p in data.products.items()}
    return {
        "products": len(data.products),
        "products_optimized": len(data.products) - len(failures),
        "failures": failures,
        "fallback_products": fallbacks,
        "series_forecast": len(forecasts),
        "forecast_methods": dict(Counter(f["method"] for f in forecasts.values())),
        "demand_patterns": dict(Counter(f["pattern"] for f in forecasts.values())),
        "median_mase": round(statistics.median(mases), 4) if mases else None,
        "nodes_optimized": len(results),
        "total_safety_stock_units": round(sum(r["safety_stock"] for r in results.values()), 1),
        "safety_stock_value": round(
            sum(r["safety_stock"] * unit_cost[p] for (_, p), r in results.items()), 2),
        "holding_cost_per_day": round(
            sum(r["safety_stock_cost"] for r in results.values()), 2),
        "stockout_alerts": stockout_alerts,
        "transportation": transport,
        "horizon": horizon,
        "history_days": history_days,
        "history_end": end.date().isoformat(),
        "duration_seconds": round(time.perf_counter() - started, 2),
    }


def execute_network_run(
    session_factory: Callable[[], Session], run_id: str, params: Dict[str, Any]
) -> None:
    """Background entry point: owns its session and records success or failure on the run."""
    db = session_factory()
    run_repo = PipelineRunRepository(db)
    try:
        summary = run_network_pipeline(db, run_id, params)
        run_repo.set_summary(run_id, summary)
        run_repo.complete(
            run_id=run_id,
            status="success",
            solver="heuristic" if summary["fallback_products"] else "cp-sat",
            fallback_used=bool(summary["fallback_products"]),
            duration=summary["duration_seconds"],
        )
        log.info(f"pipeline_run={run_id} network run complete: {summary['nodes_optimized']} nodes")
    except Exception as e:
        log.exception(f"pipeline_run={run_id} network run failed")
        run_repo.fail(run_id=run_id, error=str(e))
    finally:
        db.close()
