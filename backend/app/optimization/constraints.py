"""
Optimization Constraints.
Shared constraint builders for both CP-SAT and LP solvers.
"""
from typing import List, Dict
from app.optimization.gsm import GSMNetwork


def build_service_time_bounds(network: GSMNetwork) -> Dict[str, Dict]:
    """
    Builds lower and upper bounds for S_in and S_out at each node.
    S_out bounds are defined directly on the node (min_s_out / max_s_out).
    S_in is driven by the upstream S_out + transit time.
    """
    node_map = network.node_map()
    bounds = {}
    for node in network.nodes:
        bounds[node.id] = {
            "s_out_lb": node.min_s_out,
            "s_out_ub": node.max_s_out,
            "s_in_lb": 0,
            "s_in_ub": sum(e.transit_time for e in network.edges) + sum(n.processing_time for n in network.nodes),
        }
    return bounds


def validate_net_replenishment_times(
    net_times: Dict[str, int],
    max_allowed: int = 365,
) -> List[str]:
    """
    Validates that computed net replenishment times are within acceptable bounds.
    Returns list of violations.
    """
    violations = []
    for node_id, t in net_times.items():
        if t < 0:
            violations.append(f"Node '{node_id}': Net replenishment time {t} is negative.")
        if t > max_allowed:
            violations.append(f"Node '{node_id}': Net replenishment time {t} exceeds max {max_allowed} days.")
    return violations


def check_capacity_constraints(
    safety_stocks: Dict[str, float],
    node_capacities: Dict[str, float],
) -> List[str]:
    """
    Checks if the computed safety stock quantities exceed node capacity.
    Returns a list of violations.
    """
    violations = []
    for node_id, ss in safety_stocks.items():
        capacity = node_capacities.get(node_id)
        if capacity is not None and ss > capacity:
            violations.append(
                f"Node '{node_id}': Safety stock {ss:.1f} exceeds capacity {capacity:.1f}."
            )
    return violations
