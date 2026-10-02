"""
Heuristic fallback solver for GSM.
Used when CP-SAT times out or finds no feasible solution within the service-time bounds.
"""
import math
import time
from typing import Any, Dict

from app.optimization.gsm import GSMNetwork
from app.optimization.service_time import get_z_score


def run_heuristic_solver(network: GSMNetwork) -> Dict[str, Any]:
    """
    Greedy pass in topological order: each node quotes the largest outbound service
    time it is allowed, driving its own net replenishment time towards zero.
    Not globally optimal, but fast, deterministic and always feasible.
    """
    start = time.perf_counter()
    node_map = network.node_map()
    s_in: Dict[str, int] = {}
    s_out: Dict[str, int] = {}

    for node_id in network.topological_order():
        node = node_map[node_id]
        s_in[node_id] = max(
            (s_out[p] + network.transit_time(p, node_id) for p in network.predecessors(node_id)),
            default=0,
        )
        available = s_in[node_id] + node.processing_time
        s_out[node_id] = min(node.max_s_out, available)

    results = {}
    total_cost = 0.0
    for node in network.nodes:
        n_id = node.id
        net_time = max(0, s_in[n_id] + node.processing_time - s_out[n_id])
        ss = get_z_score(node.service_level) * node.demand_std * math.sqrt(net_time)
        ss_cost = ss * node.holding_cost
        total_cost += ss_cost
        results[n_id] = {
            "s_in": s_in[n_id],
            "s_out": s_out[n_id],
            "net_replenishment_time": net_time,
            "safety_stock_cost": round(ss_cost, 2),
        }

    return {
        "status": "FEASIBLE",
        "objective_value": round(total_cost, 2),
        "wall_time": time.perf_counter() - start,
        "nodes": results,
    }
