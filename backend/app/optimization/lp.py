"""
LP Fallback Solver for GSM.
Used when CP-SAT exceeds the configured timeout (OPTIMIZATION_TIMEOUT_SECONDS).
Uses scipy.optimize.linprog as a lightweight linear programming fallback.
"""
import math
from typing import Dict, Any, List
from app.optimization.gsm import GSMNetwork
from app.optimization.service_time import get_z_score


def run_lp_solver(network: GSMNetwork) -> Dict[str, Any]:
    """
    LP Fallback: Solves the safety stock minimization problem using a greedy heuristic.
    Sets each node's S_out to its maximum allowed value to minimize net replenishment time,
    which in turn minimizes safety stock at each stage.

    This is NOT globally optimal, but is fast, always feasible, and deterministic.
    Used as a fallback when CP-SAT times out.
    """
    node_map = network.node_map()
    s_out: Dict[str, int] = {}
    s_in: Dict[str, int] = {}

    # Process nodes in topological order (sources first)
    ordered = _topological_sort(network)

    for node_id in ordered:
        node = node_map[node_id]
        preds = network.predecessors(node_id)

        if not preds:
            # Source node: S_in = 0
            s_in[node_id] = 0
        else:
            # S_in = max upstream(S_out[src] + transit_time)
            s_in[node_id] = max(
                s_out.get(src, 0) + network.transit_time(src, node_id)
                for src in preds
            )

        # Greedy: always use maximum allowed S_out to minimize T
        net_time = s_in[node_id] + node.processing_time
        # S_out = min(max_s_out, net_time) so that T >= 0
        s_out[node_id] = min(node.max_s_out, net_time)

    # Compute net replenishment times and safety stocks
    results = {}
    total_cost = 0.0
    for node in network.nodes:
        n_id = node.id
        net_time = max(0, s_in.get(n_id, 0) + node.processing_time - s_out.get(n_id, 0))
        z = get_z_score(node.service_level)
        ss = z * node.demand_std * math.sqrt(net_time) if net_time > 0 else 0.0
        ss_cost = ss * node.holding_cost
        total_cost += ss_cost
        results[n_id] = {
            "s_in": s_in.get(n_id, 0),
            "s_out": s_out.get(n_id, 0),
            "net_replenishment_time": net_time,
            "safety_stock": round(ss, 2),
            "safety_stock_cost": round(ss_cost, 2),
        }

    return {
        "status": "FEASIBLE",
        "fallback_used": True,
        "objective_value": round(total_cost, 2),
        "wall_time": 0.0,
        "nodes": results,
    }


def _topological_sort(network: GSMNetwork) -> List[str]:
    """Kahn's algorithm for topological ordering of the network."""
    from collections import deque
    in_degree = {n.id: 0 for n in network.nodes}
    for e in network.edges:
        in_degree[e.target] = in_degree.get(e.target, 0) + 1

    queue = deque([n for n, d in in_degree.items() if d == 0])
    order = []
    while queue:
        node = queue.popleft()
        order.append(node)
        for e in network.edges:
            if e.source == node:
                in_degree[e.target] -= 1
                if in_degree[e.target] == 0:
                    queue.append(e.target)
    return order
