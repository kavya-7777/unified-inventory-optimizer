"""
Transportation Optimization using Linear Programming.
Minimizes freight costs across the supply chain network.
"""
from typing import Any, Dict, List

import numpy as np
from scipy import sparse
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


def optimize_transportation_multi_sku(
    lanes: List[Dict[str, Any]],
    skus_demand: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Joint multi-commodity LP over all lanes and SKUs, so a lane's capacity is shared by
    every SKU routed through it.

    lanes: [{id, source_id, target_id, cost_per_unit, capacity, transit_time}, ...]
    skus_demand: [{product_id, sku, demand_by_location: {location_id: demand},
                   lane_ids (optional): lanes this SKU may use}, ...]
    Locations without an entry are pass-through nodes; nodes with no inbound lane supply
    whatever is required.
    """
    num_lanes = len(lanes)
    num_skus = len(skus_demand)
    if num_lanes == 0 or num_skus == 0:
        return {"status": "NO_EDGES", "lane_flows": [], "total_cost": 0.0}

    def var(lane_idx: int, sku_idx: int) -> int:
        return lane_idx * num_skus + sku_idx

    num_vars = num_lanes * num_skus
    costs = np.repeat([float(lane.get("cost_per_unit") or 0.0) for lane in lanes], num_skus)

    targets = {lane["target_id"] for lane in lanes}
    balance_nodes = sorted(targets)
    node_row = {n: i for i, n in enumerate(balance_nodes)}

    eq_rows, eq_cols, eq_vals = [], [], []
    for l_idx, lane in enumerate(lanes):
        for s_idx in range(num_skus):
            col = var(l_idx, s_idx)
            eq_rows.append(node_row[lane["target_id"]] * num_skus + s_idx)
            eq_cols.append(col)
            eq_vals.append(1.0)
            if lane["source_id"] in node_row:
                eq_rows.append(node_row[lane["source_id"]] * num_skus + s_idx)
                eq_cols.append(col)
                eq_vals.append(-1.0)
    a_eq = sparse.csr_matrix(
        (eq_vals, (eq_rows, eq_cols)), shape=(len(balance_nodes) * num_skus, num_vars)
    )
    b_eq = np.array([
        float(sku.get("demand_by_location", {}).get(node, 0.0))
        for node in balance_nodes
        for sku in skus_demand
    ])

    capacitated = [i for i, lane in enumerate(lanes) if (lane.get("capacity") or 0) > 0]
    a_ub = b_ub = None
    if capacitated:
        ub_rows = [r for r in range(len(capacitated)) for _ in range(num_skus)]
        ub_cols = [var(l_idx, s) for l_idx in capacitated for s in range(num_skus)]
        a_ub = sparse.csr_matrix(
            (np.ones(len(ub_cols)), (ub_rows, ub_cols)), shape=(len(capacitated), num_vars)
        )
        b_ub = np.array([float(lanes[i]["capacity"]) for i in capacitated])

    bounds = [
        (0.0, 0.0) if "lane_ids" in sku and lane["id"] not in sku["lane_ids"] else (0.0, None)
        for lane in lanes
        for sku in skus_demand
    ]
    res = linprog(
        costs, A_eq=a_eq, b_eq=b_eq, A_ub=a_ub, b_ub=b_ub, bounds=bounds, method="highs"
    )
    if not res.success:
        return {"status": "INFEASIBLE", "message": res.message, "lane_flows": [],
                "total_cost": 0.0}

    lane_flows = []
    for l_idx, lane in enumerate(lanes):
        cap = lane.get("capacity")
        unit_cost = float(lane.get("cost_per_unit") or 0.0)
        for s_idx, sku in enumerate(skus_demand):
            qty = round(float(res.x[var(l_idx, s_idx)]), 2)
            if qty <= 0:
                continue
            lane_flows.append({
                "lane_id": lane["id"],
                "source_id": lane["source_id"],
                "target_id": lane["target_id"],
                "product_id": sku["product_id"],
                "sku": sku.get("sku"),
                "quantity": qty,
                "capacity": cap,
                "utilization": round(qty / cap, 4) if cap else None,
                "transit_time": lane.get("transit_time"),
                "cost": round(qty * unit_cost, 2),
            })

    total_capacity = sum(float(lanes[i]["capacity"]) for i in capacitated)
    used_capacity = sum(float(res.x[var(i, s)]) for i in capacitated for s in range(num_skus))
    utilization = round(used_capacity / total_capacity, 4) if total_capacity > 0 else None

    return {
        "status": "OPTIMAL",
        "total_cost": round(float(res.fun), 2),
        "planned_units": round(sum(f["quantity"] for f in lane_flows), 2),
        "capacity_utilization": utilization,
        "active_lanes": len({f["lane_id"] for f in lane_flows}),
        "lane_flows": lane_flows,
    }
