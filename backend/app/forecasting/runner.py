"""
Forecasting Pipeline Runner.
Routes each SKU to the most appropriate model based on demand classification.
"""
from typing import List, Dict, Any

from app.forecasting.classifier import classify_demand, DemandPattern
from app.forecasting.ets import simple_exponential_smoothing, double_exponential_smoothing
from app.forecasting.croston import croston_sba


def run_forecast_pipeline(items: List[Dict[str, Any]], horizon: int = 4) -> List[Dict[str, Any]]:
    """
    For each item with demand history, classify demand and apply the appropriate model.
    
    items format: [{"id": "P1", "history": [10, 0, 15, 0, 8, ...], "has_trend": false}]
    Returns list of forecasts with model used and method.
    """
    results = []
    for item in items:
        item_id = item.get("id", "unknown")
        history = item.get("history", [])
        has_trend = item.get("has_trend", False)

        if len(history) < 2:
            results.append({
                "id": item_id,
                "forecast": [0.0] * horizon,
                "method": "ZERO",
                "pattern": "INSUFFICIENT_DATA",
            })
            continue

        pattern = classify_demand(history)
        
        if pattern in (DemandPattern.INTERMITTENT, DemandPattern.LUMPY):
            result = croston_sba(history, horizon=horizon)
        elif has_trend:
            result = double_exponential_smoothing(history, horizon=horizon)
        else:
            result = simple_exponential_smoothing(history, horizon=horizon)

        results.append({
            "id": item_id,
            "forecast": result["forecast"],
            "method": result["method"],
            "pattern": pattern.value,
        })

    return results
