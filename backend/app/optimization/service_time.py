"""
Service Time Calculator.
Computes the net replenishment time for each node in a GSM network
given a solved set of inbound and outbound service times.
"""
import math
from functools import lru_cache
from typing import Dict

from scipy.stats import norm

from app.optimization.gsm import GSMNetwork


@lru_cache(maxsize=256)
def get_z_score(service_level: float) -> float:
    """Inverse standard normal CDF for a cycle service level in (0, 1)."""
    if not 0 < service_level < 1:
        raise ValueError(f"Service level must be in (0, 1), got {service_level}")
    return float(norm.ppf(service_level))


def compute_inbound_service_times(
    network: GSMNetwork,
    s_out: Dict[str, int],
) -> Dict[str, int]:
    """S_in_j = max over predecessors i of (S_out_i + transit_ij); 0 for source nodes."""
    s_in = {}
    for node in network.nodes:
        preds = network.predecessors(node.id)
        s_in[node.id] = max(
            (s_out.get(p, 0) + network.transit_time(p, node.id) for p in preds),
            default=0,
        )
    return s_in


def compute_net_replenishment_times(
    network: GSMNetwork,
    s_in: Dict[str, int],
    s_out: Dict[str, int],
) -> Dict[str, int]:
    """
    Computes T_i = S_in_i + ProcessingTime_i - S_out_i for all nodes.
    This is the net replenishment time that drives safety stock.
    """
    net_times = {}
    for node in network.nodes:
        t = s_in.get(node.id, 0) + node.processing_time - s_out.get(node.id, 0)
        net_times[node.id] = max(0, t)
    return net_times


def compute_safety_stock_quantities(
    network: GSMNetwork,
    net_replenishment_times: Dict[str, int],
) -> Dict[str, float]:
    """SS_i = Z_i * sigma_i * sqrt(T_i)"""
    node_map = network.node_map()
    safety_stocks = {}
    for node_id, net_time in net_replenishment_times.items():
        node = node_map[node_id]
        if net_time > 0 and node.demand_std > 0:
            ss = get_z_score(node.service_level) * node.demand_std * math.sqrt(net_time)
        else:
            ss = 0.0
        safety_stocks[node_id] = round(max(ss, 0.0), 2)
    return safety_stocks


def compute_reorder_points(
    network: GSMNetwork,
    net_replenishment_times: Dict[str, int],
    safety_stocks: Dict[str, float],
) -> Dict[str, float]:
    """ROP_i = demand_mean_i * T_i + SS_i"""
    node_map = network.node_map()
    rops = {}
    for node_id, net_time in net_replenishment_times.items():
        node = node_map[node_id]
        rop = node.demand_mean * net_time + safety_stocks.get(node_id, 0.0)
        rops[node_id] = round(rop, 2)
    return rops
