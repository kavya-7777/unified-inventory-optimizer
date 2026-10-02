"""Batch forecasting entry point used by the forecast and sandbox pipeline endpoints."""
from typing import Any, Dict, List

from app.forecasting.engine import batch_forecast


def run_forecast_pipeline(items: List[Dict[str, Any]], horizon: int = 4) -> List[Dict[str, Any]]:
    """
    items format: [{"id": "P1", "history": [10, 0, 15, 0, 8, ...], "has_trend": null}]
    """
    return [
        {
            "id": r["id"],
            "forecast": r["forecast"],
            "lower": r["lower"],
            "upper": r["upper"],
            "method": r["method"],
            "pattern": r["pattern"],
            "demand_std": r["demand_std"],
            "mase": (r["metrics"] or {}).get("mase"),
            "mape": (r["metrics"] or {}).get("mape"),
        }
        for r in batch_forecast(items, horizon)
    ]
