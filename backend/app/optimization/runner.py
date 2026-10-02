"""
MEIO Optimization Pipeline Runner.
Orchestrates: Network Validation → CP-SAT (GSM) → Heuristic Fallback → SS, ROP, EOQ
"""
import logging
import time
import uuid
from typing import Any, Dict, List

from app.core.config import settings
from app.optimization.constraints import check_capacity_constraints
from app.optimization.cp_sat import run_gsm_solver
from app.optimization.errors import NetworkValidationError
from app.optimization.gsm import build_network_from_dicts
from app.optimization.heuristic import run_heuristic_solver
from app.optimization.reorder_point import calculate_order_quantity
from app.optimization.service_time import (
    compute_inbound_service_times,
    compute_net_replenishment_times,
    compute_reorder_points,
    compute_safety_stock_quantities,
)

log = logging.getLogger(__name__)

DAYS_PER_YEAR = 365
DEFAULT_MAX_SERVICE_TIME = 30


def run_optimization_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main MEIO optimization entrypoint.

    Raises NetworkValidationError if the network is malformed.
    """
    pipeline_run_id = params.get("pipeline_run_id") or str(uuid.uuid4())
    start_time = time.perf_counter()

    node_dicts = params.get("nodes") or default_demo_nodes()
    edge_dicts = params.get("edges") or default_demo_edges()
    network = build_network_from_dicts(node_dicts, edge_dicts)

    errors = network.validate()
    if errors:
        raise NetworkValidationError(errors)

    max_service_time = params.get("max_service_time")
    if max_service_time is None:
        max_service_time = DEFAULT_MAX_SERVICE_TIME

    log.info(f"pipeline_run={pipeline_run_id} starting optimization nodes={len(network.nodes)}")

    solver_result = run_gsm_solver(
        network,
        max_time=max_service_time,
        timeout_seconds=float(settings.OPTIMIZATION_TIMEOUT_SECONDS),
    )
    fallback_used = solver_result["status"] not in ("OPTIMAL", "FEASIBLE")
    if fallback_used:
        log.warning(
            f"pipeline_run={pipeline_run_id} CP-SAT status={solver_result['status']}, "
            "falling back to heuristic"
        )
        solver_result = run_heuristic_solver(network)

    s_out = {n_id: v["s_out"] for n_id, v in solver_result["nodes"].items()}
    s_in = compute_inbound_service_times(network, s_out)
    net_times = compute_net_replenishment_times(network, s_in, s_out)
    safety_stocks = compute_safety_stock_quantities(network, net_times)
    reorder_points = compute_reorder_points(network, net_times, safety_stocks)

    capacity_violations = check_capacity_constraints(
        safety_stocks, params.get("node_capacities") or {}
    )

    node_results = {}
    for node in network.nodes:
        n_id = node.id
        node_results[n_id] = {
            "s_in": s_in[n_id],
            "s_out": s_out[n_id],
            "net_replenishment_time": net_times[n_id],
            "safety_stock": safety_stocks[n_id],
            "reorder_point": reorder_points[n_id],
            "order_quantity": calculate_order_quantity(
                annual_demand=node.demand_mean * DAYS_PER_YEAR,
                ordering_cost=node.ordering_cost,
                holding_cost_per_unit=node.holding_cost * DAYS_PER_YEAR,
            ),
            "safety_stock_cost": round(safety_stocks[n_id] * node.holding_cost, 2),
            "location_id": node.location_id,
            "product_id": node.product_id,
        }

    total_duration = time.perf_counter() - start_time
    log.info(
        f"pipeline_run={pipeline_run_id} completed status={solver_result['status']} "
        f"fallback={fallback_used} duration={total_duration:.3f}s"
    )

    return {
        "pipeline_run_id": pipeline_run_id,
        "run_type": params.get("run_type", "manual"),
        "status": solver_result["status"],
        "solver": "heuristic" if fallback_used else "cp-sat",
        "fallback_used": fallback_used,
        "objective_value": solver_result.get("objective_value"),
        "solver_duration_seconds": round(solver_result.get("wall_time", 0.0), 4),
        "total_duration_seconds": round(total_duration, 4),
        "capacity_violations": capacity_violations,
        "node_results": node_results,
    }


def default_demo_nodes() -> List[Dict[str, Any]]:
    return [
        {"id": "Supplier", "type": "Supplier", "processing_time": 2, "demand_std": 0,
         "demand_mean": 0, "holding_cost": 1, "max_s_out": 10, "service_level": 0.95},
        {"id": "DC1", "type": "DC", "processing_time": 1, "demand_std": 50,
         "demand_mean": 200, "holding_cost": 5, "max_s_out": 5, "service_level": 0.95},
        {"id": "Store1", "type": "Store", "processing_time": 0, "demand_std": 20,
         "demand_mean": 100, "holding_cost": 10, "max_s_out": 0, "service_level": 0.95},
    ]


def default_demo_edges() -> List[Dict[str, Any]]:
    return [
        {"source": "Supplier", "target": "DC1", "transit_time": 3},
        {"source": "DC1", "target": "Store1", "transit_time": 1},
    ]
