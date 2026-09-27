"""
Transportation Optimization using Linear Programming.
Minimizes freight costs across the supply chain network.
"""
from typing import Dict, Any, List
from scipy.optimize import linprog

def optimize_transportation(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Given a network with demands and lanes, optimize the flow to minimize transport cost.
    Requires:
      - node["demand_mean"]: for sink nodes (demand out)
      - edge["cost_per_unit"]: cost to ship one unit on this lane
      - edge["capacity"]: maximum units that can be shipped on this lane
    """
    # 1. Map nodes to indices
    node_indices = {n["id"]: idx for idx, n in enumerate(nodes)}
    num_nodes = len(nodes)
    num_edges = len(edges)
    
    if num_edges == 0:
        return {"status": "NO_EDGES", "flows": {}}

    # 2. Objective function: minimize sum(flow_e * cost_e)
    c = []
    for e in edges:
        c.append(e.get("cost_per_unit", 1.0))
        
    # 3. Flow conservation constraints (A_eq * x = b_eq)
    # flow_in - flow_out = demand for non-source nodes
    A_eq = []
    b_eq = []
    
    # Find sources
    targets = {e["target"] for e in edges}
    sources = [n["id"] for n in nodes if n["id"] not in targets]
    
    for n in nodes:
        if n["id"] in sources:
            continue # Flow is unconstrained at source (can supply as much as needed)
            
        row = [0] * num_edges
        for e_idx, e in enumerate(edges):
            if e["target"] == n["id"]:
                row[e_idx] = 1.0  # flow in
            elif e["source"] == n["id"]:
                row[e_idx] = -1.0 # flow out
        A_eq.append(row)
        b_eq.append(n.get("demand_mean", 0.0))
        
    # 4. Bounds (0 <= flow <= capacity)
    bounds = []
    for e in edges:
        cap = e.get("capacity", None)
        if cap is None or cap <= 0:
            bounds.append((0, None))
        else:
            bounds.append((0, cap))
            
    # 5. Solve
    res = linprog(c, A_eq=A_eq if A_eq else None, b_eq=b_eq if b_eq else None, bounds=bounds, method='highs')
    
    if res.success:
        flows = {}
        for e_idx, e in enumerate(edges):
            lane_id = f"{e['source']}->{e['target']}"
            flows[lane_id] = round(res.x[e_idx], 2)

        return {
            "status": "OPTIMAL",
            "total_cost": round(res.fun, 2),
            "flows": flows
        }
    else:
        return {
            "status": "INFEASIBLE",
            "message": res.message,
            "flows": {}
        }


def optimize_transportation_multi_sku(
    lanes: List[Dict[str, Any]],
    skus_demand: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Multi-commodity extension of `optimize_transportation`: solves one joint LP across
    all lanes AND all SKUs simultaneously, so that a lane's capacity is correctly shared
    across every SKU flowing through it (solving each SKU independently would let every
    SKU assume it alone has the full lane capacity).

    lanes: [{id, source_id, target_id, cost_per_unit, capacity (optional, None = unconstrained), transit_time}, ...]
    skus_demand: [{product_id, sku, demand_by_location: {location_id: demand_mean, ...}}, ...]
                 Only locations with real demand (e.g. Stores) need an entry; any node
                 not present is treated as a pure pass-through (net demand 0), exactly
                 like `optimize_transportation`'s "sources" have unconstrained supply.

    Returns per-(lane, sku) flow, plus per-lane aggregate utilization/cost.
    """
    num_lanes = len(lanes)
    num_skus = len(skus_demand)

    if num_lanes == 0 or num_skus == 0:
        return {"status": "NO_EDGES", "lane_flows": [], "total_cost": 0.0}

    def var_idx(lane_idx: int, sku_idx: int) -> int:
        return lane_idx * num_skus + sku_idx

    num_vars = num_lanes * num_skus

    # Objective: minimize sum(cost_per_unit_lane * x[lane, sku]) over all lane/sku pairs.
    c = [0.0] * num_vars
    for l_idx, lane in enumerate(lanes):
        cost = lane.get("cost_per_unit", 1.0)
        for s_idx in range(num_skus):
            c[var_idx(l_idx, s_idx)] = cost

    node_ids = sorted({lane["source_id"] for lane in lanes} | {lane["target_id"] for lane in lanes})
    targets = {lane["target_id"] for lane in lanes}
    source_nodes = [n for n in node_ids if n not in targets]  # unconstrained upstream supply

    # Flow-balance equality constraints: one row per (non-source node, sku).
    A_eq: List[List[float]] = []
    b_eq: List[float] = []
    for node_id in node_ids:
        if node_id in source_nodes:
            continue
        for s_idx, sku in enumerate(skus_demand):
            row = [0.0] * num_vars
            for l_idx, lane in enumerate(lanes):
                if lane["target_id"] == node_id:
                    row[var_idx(l_idx, s_idx)] = 1.0
                elif lane["source_id"] == node_id:
                    row[var_idx(l_idx, s_idx)] = -1.0
            A_eq.append(row)
            b_eq.append(sku.get("demand_by_location", {}).get(node_id, 0.0))

    # Shared-capacity inequality constraints: one row per capacitated lane, summed over all SKUs.
    A_ub: List[List[float]] = []
    b_ub: List[float] = []
    for l_idx, lane in enumerate(lanes):
        cap = lane.get("capacity")
        if cap is not None and cap > 0:
            row = [0.0] * num_vars
            for s_idx in range(num_skus):
                row[var_idx(l_idx, s_idx)] = 1.0
            A_ub.append(row)
            b_ub.append(cap)

    bounds = [(0, None)] * num_vars

    res = linprog(
        c,
        A_eq=A_eq if A_eq else None,
        b_eq=b_eq if b_eq else None,
        A_ub=A_ub if A_ub else None,
        b_ub=b_ub if b_ub else None,
        bounds=bounds,
        method="highs",
    )

    if not res.success:
        return {"status": "INFEASIBLE", "message": res.message, "lane_flows": []}

    lane_flows = []
    for l_idx, lane in enumerate(lanes):
        cap = lane.get("capacity")
        cost_per_unit = lane.get("cost_per_unit", 1.0)
        for s_idx, sku in enumerate(skus_demand):
            qty = round(res.x[var_idx(l_idx, s_idx)], 2)
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
                "cost": round(qty * cost_per_unit, 2),
            })

    total_cost = round(res.fun, 2)
    capacitated = [lane for lane in lanes if lane.get("capacity")]
    total_capacity = sum(lane["capacity"] for lane in capacitated)
    used_capacity = sum(
        res.x[var_idx(l_idx, s_idx)]
        for l_idx, lane in enumerate(lanes) if lane.get("capacity")
        for s_idx in range(num_skus)
    )
    capacity_utilization = (used_capacity / total_capacity) if total_capacity > 0 else None

    return {
        "status": "OPTIMAL",
        "total_cost": total_cost,
        "planned_units": round(sum(f["quantity"] for f in lane_flows), 2),
        "capacity_utilization": round(capacity_utilization, 4) if capacity_utilization is not None else None,
        "active_lanes": len({f["lane_id"] for f in lane_flows}),
        "lane_flows": lane_flows,
    }
