"""
MEIO Optimization Pipeline Runner.
Orchestrates: Network Validation → CP-SAT (GSM) → LP Fallback → SS Calculation → ROP
"""
import uuid
import time
import logging
from typing import Dict, Any

from app.core.config import settings
from app.optimization.gsm import GSMNetwork, GSMNode, GSMEdge, build_network_from_dicts
from app.optimization.cp_sat import run_gsm_solver
from app.optimization.lp import run_lp_solver
from app.optimization.service_time import (
    compute_net_replenishment_times,
    compute_safety_stock_quantities,
    compute_reorder_points,
)
from app.optimization.constraints import validate_net_replenishment_times, check_capacity_constraints

log = logging.getLogger(__name__)


def run_optimization_pipeline(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main MEIO Optimization Pipeline entrypoint.

    Flow:
        1. Build & validate GSM network from request params
        2. Run CP-SAT solver (with timeout)
        3. Fallback to LP if CP-SAT exceeds timeout
        4. Compute safety stock quantities and reorder points
        5. Return structured result with full audit trail
    """
    pipeline_run_id = params.get("pipeline_run_id") or str(uuid.uuid4())
    start_time = time.time()
    fallback_used = False

    log.info(f"pipeline_run={pipeline_run_id} starting optimization")

    # 1. Build network — use defaults if nodes/edges not provided or explicitly None
    node_dicts = params.get("nodes") or _default_demo_nodes()
    edge_dicts = params.get("edges") or _default_demo_edges()
    network = build_network_from_dicts(node_dicts, edge_dicts)

    # Validate
    errors = network.validate()
    if errors:
        return {
            "pipeline_run_id": pipeline_run_id,
            "status": "INVALID_DATA",
            "errors": errors,
        }

    # 2. Attempt CP-SAT
    timeout = settings.OPTIMIZATION_TIMEOUT_SECONDS
    solver_result = run_gsm_solver(
        node_dicts, edge_dicts, max_time=params.get("max_service_time", 30)
    )

    # 3. LP Fallback if CP-SAT timed out or infeasible
    if solver_result["status"] not in ("OPTIMAL", "FEASIBLE"):
        log.warning(f"pipeline_run={pipeline_run_id} CP-SAT status={solver_result['status']}, falling back to LP")
        solver_result = run_lp_solver(network)
        fallback_used = True

    # 4. Compute quantities from solver service times
    s_in = {n_id: v["s_in"] for n_id, v in solver_result["nodes"].items()}
    s_out = {n_id: v["s_out"] for n_id, v in solver_result["nodes"].items()}

    net_times = compute_net_replenishment_times(network, s_in, s_out)
    safety_stocks = compute_safety_stock_quantities(network, net_times)
    reorder_points = compute_reorder_points(network, net_times, safety_stocks)

    # 5. Constraint checks
    capacity_violations = check_capacity_constraints(
        safety_stocks, params.get("node_capacities") or {}
    )

    total_duration = time.time() - start_time
    log.info(
        f"pipeline_run={pipeline_run_id} completed "
        f"status={solver_result['status']} "
        f"fallback={fallback_used} "
        f"duration={total_duration:.3f}s"
    )

    # 6. Build output
    node_results = {}
    for node in network.nodes:
        n_id = node.id
        node_results[n_id] = {
            "s_in": s_in.get(n_id, 0),
            "s_out": s_out.get(n_id, 0),
            "net_replenishment_time": net_times.get(n_id, 0),
            "safety_stock": safety_stocks.get(n_id, 0.0),
            "reorder_point": reorder_points.get(n_id, 0.0),
        }

    return {
        "pipeline_run_id": pipeline_run_id,
        "run_type": params.get("run_type", "manual"),
        "status": solver_result["status"],
        "solver": "lp-fallback" if fallback_used else "cp-sat",
        "fallback_used": fallback_used,
        "objective_value": solver_result.get("objective_value"),
        "solver_duration_seconds": solver_result.get("wall_time", 0.0),
        "total_duration_seconds": round(total_duration, 4),
        "capacity_violations": capacity_violations,
        "node_results": node_results,
    }


def _default_demo_nodes():
    return [
        {"id": "Supplier", "type": "Supplier", "processing_time": 2, "demand_std": 0, "demand_mean": 0, "holding_cost": 1, "max_s_out": 10, "min_s_out": 0, "service_level": 0.95},
        {"id": "DC1", "type": "DC", "processing_time": 1, "demand_std": 50, "demand_mean": 200, "holding_cost": 5, "max_s_out": 5, "min_s_out": 0, "service_level": 0.95},
        {"id": "Store1", "type": "Store", "processing_time": 0, "demand_std": 20, "demand_mean": 100, "holding_cost": 10, "max_s_out": 0, "min_s_out": 0, "service_level": 0.95},
    ]


def _default_demo_edges():
    return [
        {"source": "Supplier", "target": "DC1", "transit_time": 3},
        {"source": "DC1", "target": "Store1", "transit_time": 1},
    ]

