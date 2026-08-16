"""
Exponential Smoothing (ETS) Forecaster.
Used for smooth/erratic demand patterns.
"""
from typing import List, Dict, Any


def simple_exponential_smoothing(history: List[float], alpha: float = 0.3, horizon: int = 4) -> Dict[str, Any]:
    """
    Single Exponential Smoothing (SES / Simple ETS).
    Works well for smooth demand with no trend or seasonality.
    
    S_t = alpha * D_t + (1 - alpha) * S_{t-1}
    Forecast = last smoothed value (constant forecast)
    """
    if not history:
        return {"forecast": [], "fitted": [], "alpha": alpha}

    smoothed = [history[0]]
    for i in range(1, len(history)):
        s = alpha * history[i] + (1 - alpha) * smoothed[-1]
        smoothed.append(s)

    forecast = [smoothed[-1]] * horizon

    return {
        "forecast": [round(f, 2) for f in forecast],
        "fitted": [round(s, 2) for s in smoothed],
        "alpha": alpha,
        "method": "SES",
    }


def double_exponential_smoothing(
    history: List[float],
    alpha: float = 0.3,
    beta: float = 0.1,
    horizon: int = 4,
) -> Dict[str, Any]:
    """
    Holt's Double Exponential Smoothing.
    Handles data with a trend but no seasonality.
    """
    if len(history) < 2:
        return simple_exponential_smoothing(history, alpha, horizon)

    level = [history[0]]
    trend = [history[1] - history[0]]

    for i in range(1, len(history)):
        l = alpha * history[i] + (1 - alpha) * (level[-1] + trend[-1])
        t = beta * (l - level[-1]) + (1 - beta) * trend[-1]
        level.append(l)
        trend.append(t)

    forecast = []
    for h in range(1, horizon + 1):
        forecast.append(level[-1] + h * trend[-1])

    return {
        "forecast": [round(f, 2) for f in forecast],
        "level": [round(l, 2) for l in level],
        "trend": [round(t, 2) for t in trend],
        "alpha": alpha,
        "beta": beta,
        "method": "Holt-DES",
    }
