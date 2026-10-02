import math
from typing import Any, Dict, List

from ortools.sat.python import cp_model

from app.optimization.gsm import GSMNetwork
from app.optimization.service_time import get_z_score

COST_SCALE = 1000


def calculate_precomputed_ss_costs(
    max_time: int,
    demand_std: float,
    holding_cost: float,
    service_factor: float = 1.645,
) -> List[int]:
    """
    CP-SAT only works with integers. Safety stock is proportional to sqrt(T), so the
    scaled holding cost is pre-computed for every net replenishment time T in [0, max_time].
    """
    return [
        int(round(service_factor * math.sqrt(t) * demand_std * holding_cost * COST_SCALE))
        for t in range(max_time + 1)
    ]


def run_gsm_solver(
    network: GSMNetwork,
    max_time: int = 30,
    timeout_seconds: float = 60.0,
) -> Dict[str, Any]:
    """
    Guaranteed Service Model (GSM) using Google OR-Tools CP-SAT.
    Chooses outbound service times that minimise total safety stock holding cost.
    """
    model = cp_model.CpModel()

    max_processing = max((n.processing_time for n in network.nodes), default=0)
    net_time_ub = max_time + max_processing

    s_in: Dict[str, Any] = {}
    s_out: Dict[str, Any] = {}
    net_time: Dict[str, Any] = {}
    cost: Dict[str, Any] = {}

    for node in network.nodes:
        n_id = node.id
        s_in[n_id] = model.new_int_var(0, max_time, f"s_in_{n_id}")
        s_out_ub = max(node.min_s_out, min(node.max_s_out, net_time_ub))
        s_out[n_id] = model.new_int_var(node.min_s_out, s_out_ub, f"s_out_{n_id}")
        net_time[n_id] = model.new_int_var(0, net_time_ub, f"net_time_{n_id}")
        model.add(net_time[n_id] == s_in[n_id] + node.processing_time - s_out[n_id])

        z = get_z_score(node.service_level)
        cost_array = calculate_precomputed_ss_costs(
            net_time_ub, node.demand_std, node.holding_cost, z
        )
        cost[n_id] = model.new_int_var(0, max(cost_array), f"cost_{n_id}")
        model.add_element(net_time[n_id], cost_array, cost[n_id])

    for node in network.nodes:
        preds = network.predecessors(node.id)
        if not preds:
            model.add(s_in[node.id] == 0)
            continue
        arrivals = []
        for p in preds:
            arrival = model.new_int_var(0, net_time_ub + max_time, f"arr_{p}_{node.id}")
            model.add(arrival == s_out[p] + network.transit_time(p, node.id))
            arrivals.append(arrival)
        model.add_max_equality(s_in[node.id], arrivals)

    model.minimize(sum(cost.values()))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    status = solver.solve(model)
    solved = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

    results = {}
    if solved:
        for node in network.nodes:
            n_id = node.id
            results[n_id] = {
                "s_in": solver.value(s_in[n_id]),
                "s_out": solver.value(s_out[n_id]),
                "net_replenishment_time": solver.value(net_time[n_id]),
                "safety_stock_cost": solver.value(cost[n_id]) / COST_SCALE,
            }

    return {
        "status": solver.status_name(status),
        "objective_value": solver.objective_value / COST_SCALE if solved else None,
        "wall_time": solver.wall_time,
        "nodes": results,
    }
