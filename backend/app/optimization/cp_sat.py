from ortools.sat.python import cp_model
from typing import List, Dict, Any
import math

def calculate_precomputed_ss_costs(
    max_time: int, 
    demand_std: float, 
    holding_cost: float, 
    service_factor: float = 1.645
) -> List[int]:
    """
    CP-SAT only works with integers. Safety stock is proportional to sqrt(Time).
    We pre-calculate the safety stock cost for every possible net replenishment time T (0 to max_time).
    Returns an array where index is T, and value is the scaled integer cost.
    """
    costs = []
    scaling_factor = 1000  # Scale up to preserve precision in integer math
    for t in range(max_time + 1):
        if t == 0:
            costs.append(0)
        else:
            # SS = z * sqrt(T) * demand_std
            ss = service_factor * math.sqrt(t) * demand_std
            cost = ss * holding_cost
            costs.append(int(cost * scaling_factor))
    return costs

def run_gsm_solver(
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    max_time: int = 30,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Guaranteed Service Model (GSM) using Google OR-Tools CP-SAT.
    Optimizes safety stock placement across a supply chain network.
    
    nodes format: [{"id": "DC1", "type": "DC", "processing_time": 1, "demand_std": 10, "holding_cost": 5, "max_s_out": 5}]
    edges format: [{"source": "Supplier", "target": "DC1", "transit_time": 2}]
    """
    model = cp_model.CpModel()
    
    # Compute a safe upper bound for net_time = max_time + max processing time in network
    max_processing = max((n.get("processing_time", 0) for n in nodes), default=0)
    net_time_ub = max_time + max_processing

    # 1. Variables
    s_in = {}
    s_out = {}
    net_time = {}
    cost_vars = {}
    
    total_cost_vars = []
    
    for node in nodes:
        n_id = node["id"]
        
        # Service times (in days)
        s_in[n_id] = model.NewIntVar(0, max_time, f's_in_{n_id}')
        s_out[n_id] = model.NewIntVar(0, node.get("max_s_out", max_time), f's_out_{n_id}')
        
        # Net Replenishment Time: T = S_in + ProcessingTime - S_out
        # Upper bound uses net_time_ub to avoid infeasibility on long chains
        net_time[n_id] = model.NewIntVar(0, net_time_ub, f'net_time_{n_id}')
        p_time = node.get("processing_time", 0)
        model.Add(net_time[n_id] == s_in[n_id] + p_time - s_out[n_id])
        
        # Precompute costs mapped to net_time
        cost_array = calculate_precomputed_ss_costs(
            net_time_ub, 
            node.get("demand_std", 0.0), 
            node.get("holding_cost", 0.0)
        )
        cost_vars[n_id] = model.NewIntVar(0, max(cost_array) if cost_array else 0, f'cost_{n_id}')
        model.AddElement(net_time[n_id], cost_array, cost_vars[n_id])
        
        total_cost_vars.append(cost_vars[n_id])

    # 2. Network Constraints (Edges)
    for edge in edges:
        src = edge["source"]
        tgt = edge["target"]
        t_time = edge.get("transit_time", 0)
        
        if src in s_out and tgt in s_in:
            # S_in(Target) = S_out(Source) + TransitTime
            model.Add(s_in[tgt] == s_out[src] + t_time)
            
    # For nodes with no incoming edges (e.g. root suppliers), fix S_in = 0
    targets = {e["target"] for e in edges}
    for n_id in s_in:
        if n_id not in targets:
            model.Add(s_in[n_id] == 0)

    # 3. Objective: Minimize total safety stock cost
    model.Minimize(sum(total_cost_vars))
    
    # 4. Solve — use configured timeout
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    status = solver.Solve(model)
    
    # 5. Extract Results
    results = {}
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        for node in nodes:
            n_id = node["id"]
            results[n_id] = {
                "s_in": solver.Value(s_in[n_id]),
                "s_out": solver.Value(s_out[n_id]),
                "net_replenishment_time": solver.Value(net_time[n_id]),
                "safety_stock_cost": solver.Value(cost_vars[n_id]) / 1000.0
            }
            
    return {
        "status": solver.StatusName(status),
        "objective_value": solver.ObjectiveValue() / 1000.0 if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "wall_time": solver.WallTime(),
        "nodes": results
    }

