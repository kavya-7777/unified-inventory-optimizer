def calculate_reorder_point(
    demand_mean: float, 
    lead_time_mean: float, 
    safety_stock: float
) -> float:
    """
    Calculates the Reorder Point (ROP).
    ROP = Expected Demand during Lead Time + Safety Stock
    """
    expected_lead_time_demand = demand_mean * lead_time_mean
    return expected_lead_time_demand + safety_stock

def calculate_order_quantity(
    annual_demand: float,
    ordering_cost: float,
    holding_cost_per_unit: float
) -> float:
    """
    Calculates the Economic Order Quantity (EOQ).
    EOQ = sqrt((2 * D * S) / H)
    """
    if holding_cost_per_unit <= 0:
        return 0.0
        
    import math
    eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
    return round(eoq, 2)
