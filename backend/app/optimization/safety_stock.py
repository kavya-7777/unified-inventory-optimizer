import math
from typing import Dict, List


def calculate_safety_stock(
    service_level_z: float,
    lead_time_mean: float,
    lead_time_std: float,
    demand_mean: float,
    demand_std: float,
) -> float:
    """SS = Z * sqrt(LT_mean * D_std^2 + D_mean^2 * LT_std^2)"""
    variance = lead_time_mean * demand_std**2 + demand_mean**2 * lead_time_std**2
    if variance <= 0:
        return 0.0
    return service_level_z * math.sqrt(variance)


def batch_calculate_safety_stock(items: List[Dict]) -> List[Dict]:
    """Returns copies of the input items with a 'safety_stock' field added."""
    results = []
    for item in items:
        new_item = dict(item)
        ss = calculate_safety_stock(
            service_level_z=new_item.get("service_level_z", 1.645),
            lead_time_mean=new_item.get("lead_time_mean", 1.0),
            lead_time_std=new_item.get("lead_time_std", 0.0),
            demand_mean=new_item.get("demand_mean", 0.0),
            demand_std=new_item.get("demand_std", 0.0),
        )
        new_item["safety_stock"] = round(ss, 2)
        results.append(new_item)
    return results
