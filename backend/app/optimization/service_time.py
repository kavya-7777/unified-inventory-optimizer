"""
Service Time Calculator.
Computes the net replenishment time for each node in a GSM network
given a solved set of inbound and outbound service times.
"""
import math
from typing import Dict
from app.optimization.gsm import GSMNetwork


# Standard Z-score lookup for common service levels
SERVICE_LEVEL_Z = {
    0.80: 0.842,
    0.85: 1.036,
    0.90: 1.282,
    0.95: 1.645,
    0.97: 1.881,
    0.99: 2.326,
    0.999: 3.090,
}


def get_z_score(service_level: float) -> float:
    """Returns the Z-score for a given service level, interpolating if needed."""
    if service_level in SERVICE_LEVEL_Z:
        return SERVICE_LEVEL_Z[service_level]
    # Nearest lookup
    closest = min(SERVICE_LEVEL_Z.keys(), key=lambda k: abs(k - service_level))
    return SERVICE_LEVEL_Z[closest]


def compute_net_replenishment_times(
    network: GSMNetwork,
    s_in: Dict[str, int],
    s_out: Dict[str, int],
) -> Dict[str, int]:
    """
    Computes T_i = S_in_i + ProcessingTime_i - S_out_i for all nodes.
    This is the net replenishment time that drives safety stock.
    """
    node_map = network.node_map()
    net_times = {}
    for node_id, node in node_map.items():
        t = s_in.get(node_id, 0) + node.processing_time - s_out.get(node_id, 0)
        net_times[node_id] = max(0, t)  # cannot be negative
    return net_times


def compute_safety_stock_quantities(
    network: GSMNetwork,
    net_replenishment_times: Dict[str, int],
) -> Dict[str, float]:
    """
    Given the net replenishment time from the GSM solver,
    compute the actual safety stock quantities.
    SS_i = Z_i * sigma_i * sqrt(T_i)
    """
    node_map = network.node_map()
    safety_stocks = {}
    for node_id, net_time in net_replenishment_times.items():
        node = node_map[node_id]
        z = get_z_score(node.service_level)
        if net_time > 0:
            ss = z * node.demand_std * math.sqrt(net_time)
        else:
            ss = 0.0
        safety_stocks[node_id] = round(ss, 2)
    return safety_stocks


def compute_reorder_points(
    network: GSMNetwork,
    net_replenishment_times: Dict[str, int],
    safety_stocks: Dict[str, float],
) -> Dict[str, float]:
    """
    ROP_i = demand_mean_i * T_i + SS_i
    """
    node_map = network.node_map()
    rops = {}
    for node_id, net_time in net_replenishment_times.items():
        node = node_map[node_id]
        rop = node.demand_mean * net_time + safety_stocks.get(node_id, 0.0)
        rops[node_id] = round(rop, 2)
    return rops
