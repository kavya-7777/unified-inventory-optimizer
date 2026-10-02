"""
Transportation Optimization using Linear Programming.
Minimizes freight costs across the supply chain network.
"""
from typing import Any, Dict, List

from scipy.optimize import linprog


def optimize_transportation(
    nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Min-cost flow over the lanes. Sink nodes consume their demand_mean, intermediate
    nodes conserve flow, and source nodes supply whatever is required.
      - edge["cost_per_unit"]: cost to ship one unit on this lane (default 1.0)
      - edge["capacity"]: maximum units on this lane (None or <= 0 means uncapacitated)
    """
    if not edges:
        return {"status": "NO_EDGES", "total_cost": None, "flows": {}}

    targets = {e["target"] for e in edges}
    sources = {e["source"] for e in edges}

    c = [e.get("cost_per_unit", 1.0) for e in edges]
    a_eq = []
    b_eq = []
    for n in nodes:
        n_id = n["id"]
        if n_id not in targets:
            continue
        row = [0.0] * len(edges)
        for idx, e in enumerate(edges):
            if e["target"] == n_id:
                row[idx] += 1.0
            if e["source"] == n_id:
                row[idx] -= 1.0
        a_eq.append(row)
        b_eq.append(n.get("demand_mean", 0.0) if n_id not in sources else 0.0)

    bounds = []
    for e in edges:
        cap = e.get("capacity")
        bounds.append((0, cap if cap is not None and cap > 0 else None))

    res = linprog(c, A_eq=a_eq or None, b_eq=b_eq or None, bounds=bounds, method="highs")

    if not res.success:
        return {"status": "INFEASIBLE", "total_cost": None, "message": res.message, "flows": {}}

    flows = {
        f"{e['source']}->{e['target']}": round(float(res.x[idx]), 2)
        for idx, e in enumerate(edges)
    }
    return {"status": "OPTIMAL", "total_cost": round(float(res.fun), 2), "flows": flows}
