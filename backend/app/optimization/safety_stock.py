import math
from typing import List, Dict

def calculate_safety_stock(
    service_level_z: float, 
    lead_time_mean: float, 
    lead_time_std: float, 
    demand_mean: float, 
    demand_std: float
) -> float:
    """
    Calculates safety stock using the standard probabilistic inventory model.
    SS = Z * sqrt((LeadTime_mean * Demand_std^2) + (Demand_mean^2 * LeadTime_std^2))
    """
    variance_demand_during_lt = (lead_time_mean * (demand_std ** 2)) + \
                                ((demand_mean ** 2) * (lead_time_std ** 2))
    
    # Ensure we don't sqrt a negative number due to floating point inaccuracies
    if variance_demand_during_lt <= 0:
        return 0.0
        
    return service_level_z * math.sqrt(variance_demand_during_lt)

def batch_calculate_safety_stock(items: List[Dict]) -> List[Dict]:
    """
    Processes a batch of items and appends the calculated safety stock.
    """
    results = []
    for item in items:
        ss = calculate_safety_stock(
            service_level_z=item.get("service_level_z", 1.645), # Default 95% service level
            lead_time_mean=item.get("lead_time_mean", 1.0),
            lead_time_std=item.get("lead_time_std", 0.0),
            demand_mean=item.get("demand_mean", 0.0),
            demand_std=item.get("demand_std", 0.0)
        )
        item["safety_stock"] = round(ss, 2)
        results.append(item)
    return results
