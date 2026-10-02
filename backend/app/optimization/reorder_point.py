import math


def calculate_reorder_point(
    demand_mean: float,
    lead_time_mean: float,
    safety_stock: float,
) -> float:
    """ROP = Expected Demand during Lead Time + Safety Stock"""
    return demand_mean * lead_time_mean + safety_stock


def calculate_order_quantity(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float,
) -> float:
    """EOQ = sqrt((2 * D * S) / H)"""
    if holding_cost_per_unit <= 0 or annual_demand <= 0 or ordering_cost <= 0:
        return 0.0
    eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
    return round(eoq, 2)
