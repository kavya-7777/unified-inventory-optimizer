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
    Standalone utility to process a batch of items and append calculated safety stock.
    Creates a copy of the dictionary to avoid mutating the original input.
    """
    results = []
    for item in items:
        # Create a copy to avoid in-place mutation side effects
        new_item = dict(item)
        ss = calculate_safety_stock(
            service_level_z=new_item.get("service_level_z", 1.645), # Default 95% service level
            lead_time_mean=new_item.get("lead_time_mean", 1.0),
            lead_time_std=new_item.get("lead_time_std", 0.0),
            demand_mean=new_item.get("demand_mean", 0.0),
            demand_std=new_item.get("demand_std", 0.0)
        )
        new_item["safety_stock"] = round(ss, 2)
        results.append(new_item)
    return results
