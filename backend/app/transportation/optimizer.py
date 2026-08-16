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
