"""
Automatic forecasting: classify the demand pattern, backtest the candidate models on a
holdout window, pick the most accurate one and refit it on the full history.
"""
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.forecasting.classifier import DemandPattern, demand_statistics
from app.forecasting.models import (
    INTERMITTENT_MODELS,
    SEASON,
    SMOOTH_MODELS,
    ModelFit,
    naive,
)

Z_95 = 1.96


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def accuracy(actual: Sequence[float], forecast: Sequence[float], scale: float) -> Dict[str, Any]:
    """MAE, RMSE, MAPE (over non-zero actuals), MASE and bias (mean forecast error)."""
    errors = [f - a for a, f in zip(actual, forecast)]
    mae = _mean([abs(e) for e in errors])
    rmse = math.sqrt(_mean([e * e for e in errors]))
    pct = [abs(f - a) / a for a, f in zip(actual, forecast) if a > 0]
    return {
        "mae": round(mae, 4),
        "rmse": round(rmse, 4),
        "mape": round(100 * _mean(pct), 2) if pct else None,
        "mase": round(mae / scale, 4) if scale > 0 else None,
        "bias": round(_mean(errors), 4),
    }


def _mase_scale(train: Sequence[float]) -> float:
    """In-sample MAE of the seasonal naive (or naive) forecast — the MASE denominator."""
    lag = SEASON if len(train) > SEASON else 1
    diffs = [abs(train[t] - train[t - lag]) for t in range(lag, len(train))]
    scale = _mean(diffs)
    return scale if scale > 0 else max(_mean([abs(v) for v in train]), 1.0)


def _in_sample_rmse(y: Sequence[float], fit: ModelFit) -> float:
    errs = [(a - p) ** 2 for a, p in zip(y, fit.fitted) if not math.isnan(p)]
    return math.sqrt(_mean(errs)) if errs else 0.0


def _intervals(fit: ModelFit, sigma: float) -> tuple:
    lower, upper = [], []
    for k, value in enumerate(fit.forecast, start=1):
        width = Z_95 * sigma * math.sqrt(1 + (k - 1) * fit.smoothing ** 2)
        lower.append(round(max(0.0, value - width), 2))
        upper.append(round(value + width, 2))
    return lower, upper


def forecast_series(
    history: Sequence[float],
    horizon: int = 14,
    has_trend: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Returns the selected model's forecast with 95% intervals, its holdout accuracy, a
    leaderboard of every candidate, and demand_mean / demand_std for inventory planning.
    demand_std is the forecast error (holdout RMSE), which is what safety stock protects.
    """
    y = [max(0.0, float(v)) for v in history]
    stats = demand_statistics(y)
    base: Dict[str, Any] = {**stats, "horizon": horizon, "leaderboard": [], "backtest": None}

    if len(y) < 2 or sum(y) == 0:
        level = y[-1] if y else 0.0
        method = "Zero" if y and sum(y) == 0 else "Naive"
        return {**base, "method": method, "params": {}, "forecast": [round(level, 2)] * horizon,
                "lower": [round(level, 2)] * horizon, "upper": [round(level, 2)] * horizon,
                "metrics": None, "demand_mean": round(level, 4), "demand_std": 0.0}

    pattern = stats["pattern"]
    intermittent = pattern in (DemandPattern.INTERMITTENT.value, DemandPattern.LUMPY.value)
    candidates = INTERMITTENT_MODELS if intermittent else SMOOTH_MODELS
    if has_trend is False:
        candidates = [(fn, n) for fn, n in candidates if fn.__name__ != "holt"]

    holdout = min(max(7, horizon), len(y) // 4) if len(y) >= 16 else 0
    train, test = (y[:-holdout], y[-holdout:]) if holdout else (y, [])
    scale = _mase_scale(train)

    scored: List[Tuple[Tuple[float, float], Any, ModelFit, Optional[Dict[str, Any]]]] = []
    for model, min_len in candidates:
        if len(train) < min_len:
            continue
        fit = model(train, len(test) or 1)
        if test:
            metrics = accuracy(test, fit.forecast, scale)
            key = (metrics["mase"], metrics["rmse"])
        else:
            rmse = _in_sample_rmse(train, fit)
            metrics = {"mae": None, "rmse": round(rmse, 4), "mape": None, "mase": None,
                       "bias": None}
            key = (rmse, rmse)
        scored.append((key, model, fit, metrics))

    if not scored:
        scored.append(((0.0, 0.0), naive, naive(train, len(test) or 1), None))

    scored.sort(key=lambda row: row[0])
    _, best_model, best_holdout_fit, best_metrics = scored[0]

    final = best_model(y, horizon)
    sigma = (best_metrics or {}).get("rmse") if test else None
    if not sigma:
        sigma = _in_sample_rmse(y, final)
    lower, upper = _intervals(final, sigma)

    leaderboard = [
        {"method": fit.method, "params": fit.params, **(metrics or {}),
         "selected": model is best_model}
        for _, model, fit, metrics in scored
    ]
    backtest = (
        {"actual": test, "forecast": [round(v, 2) for v in best_holdout_fit.forecast]}
        if test else None
    )
    return {
        **base,
        "method": final.method,
        "params": final.params,
        "forecast": [round(v, 2) for v in final.forecast],
        "lower": lower,
        "upper": upper,
        "metrics": best_metrics,
        "leaderboard": leaderboard,
        "backtest": backtest,
        "demand_mean": round(_mean(final.forecast), 4),
        "demand_std": round(sigma, 4),
    }


def batch_forecast(items: List[Dict[str, Any]], horizon: int) -> List[Dict[str, Any]]:
    return [
        {"id": item.get("id", "unknown"),
         **forecast_series(item.get("history") or [], horizon, item.get("has_trend"))}
        for item in items
    ]
