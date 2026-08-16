"""
Croston's Method for Intermittent and Lumpy Demand Forecasting.
Splits the forecasting into demand size and demand interval components.
"""
from typing import List, Dict, Any


def croston(
    history: List[float],
    alpha: float = 0.1,
    horizon: int = 4,
) -> Dict[str, Any]:
    """
    Croston's Method.
    Separately smooths the non-zero demand size (a) and the inter-demand interval (q).
    Forecast = a / q  (demand per period)
    """
    if not history:
        return {"forecast": [], "method": "Croston"}

    # Separate into non-zero demand sizes and intervals
    a = None  # smoothed demand size
    q = None  # smoothed interval
    last_nonzero = 0

    for i, d in enumerate(history):
        if d > 0:
            interval = i - last_nonzero
            last_nonzero = i
            if a is None:
                a = d
                q = interval if interval > 0 else 1
            else:
                a = alpha * d + (1 - alpha) * a
                q = alpha * interval + (1 - alpha) * q

    if a is None or q is None or q == 0:
        mean_demand = sum(history) / len(history)
        forecast_val = mean_demand
    else:
        forecast_val = a / q

    return {
        "forecast": [round(forecast_val, 2)] * horizon,
        "smoothed_demand_size": round(a, 2) if a else 0.0,
        "smoothed_interval": round(q, 2) if q else 0.0,
        "alpha": alpha,
        "method": "Croston",
    }


def croston_sba(
    history: List[float],
    alpha: float = 0.1,
    horizon: int = 4,
) -> Dict[str, Any]:
    """
    Croston SBA (Syntetos-Boylan Approximation).
    Applies a bias-correction factor of (1 - alpha/2) to reduce over-estimation.
    """
    result = croston(history, alpha, horizon)
    correction = 1 - alpha / 2
    corrected_forecast = [round(f * correction, 2) for f in result["forecast"]]
    result["forecast"] = corrected_forecast
    result["method"] = "Croston-SBA"
    return result
