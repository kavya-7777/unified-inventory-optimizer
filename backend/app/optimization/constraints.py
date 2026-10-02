"""Post-solve constraint checks shared by both solvers."""
from typing import Dict, List


def validate_net_replenishment_times(
    net_times: Dict[str, int],
    max_allowed: int = 365,
) -> List[str]:
    """Returns violations for net replenishment times outside [0, max_allowed]."""
    violations = []
    for node_id, t in net_times.items():
        if t < 0:
            violations.append(f"Node '{node_id}': Net replenishment time {t} is negative.")
        if t > max_allowed:
            violations.append(
                f"Node '{node_id}': Net replenishment time {t} exceeds max {max_allowed} days."
            )
    return violations


def check_capacity_constraints(
    stock_levels: Dict[str, float],
    node_capacities: Dict[str, float],
) -> List[str]:
    """Returns violations where a node's required stock exceeds its capacity."""
    violations = []
    for node_id, qty in stock_levels.items():
        capacity = node_capacities.get(node_id)
        if capacity is not None and qty > capacity:
            violations.append(
                f"Node '{node_id}': Safety stock {qty:.1f} exceeds capacity {capacity:.1f}."
            )
    return violations
