"""
Forecasting Pipeline Runner.
Routes each SKU to the most appropriate model based on demand classification.
"""
from typing import Any, Dict, List

import numpy as np

from app.forecasting.classifier import DemandPattern, classify_demand
from app.forecasting.croston import croston_sba
from app.forecasting.ets import double_exponential_smoothing, simple_exponential_smoothing


def run_forecast_pipeline(items: List[Dict[str, Any]], horizon: int = 4) -> List[Dict[str, Any]]:
    """
    For each item with demand history, classify demand and apply the appropriate model.

    items format: [{"id": "P1", "history": [10, 0, 15, 0, 8, ...], "has_trend": false}]
    """
    results = []
    for item in items:
        item_id = item.get("id", "unknown")
        history = [float(x) for x in item.get("history") or []]
        has_trend = item.get("has_trend", False)
        demand_std = float(np.std(history, ddof=1)) if len(history) > 1 else 0.0

        if len(history) < 2:
            level = history[0] if history else 0.0
            results.append({
                "id": item_id,
                "forecast": [round(level, 2)] * horizon,
                "method": "NAIVE",
                "pattern": "insufficient_data",
                "demand_std": 0.0,
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
            "demand_std": round(demand_std, 4),
        })

    return results
