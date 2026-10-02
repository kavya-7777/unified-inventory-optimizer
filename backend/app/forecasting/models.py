"""
Forecasting model library.

Every model takes a history and a horizon and returns a ModelFit holding its one-step-ahead
in-sample predictions (used to fit parameters) and its h-step forecast. Smoothing
parameters are chosen by grid search on in-sample one-step squared error.
"""
import itertools
import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple

SEASON = 7  # daily data, weekly cycle


@dataclass
class ModelFit:
    method: str
    fitted: List[float]              # one-step-ahead predictions; nan where undefined
    forecast: List[float]
    params: Dict[str, float] = field(default_factory=dict)
    smoothing: float = 0.2           # level smoothing, used to widen prediction intervals


def _sse(y: Sequence[float], fitted: Sequence[float]) -> float:
    total = 0.0
    for actual, pred in zip(y, fitted):
        if not math.isnan(pred):
            total += (actual - pred) ** 2
    return total


def _clip(values: List[float]) -> List[float]:
    return [max(0.0, v) for v in values]


def _best(candidates: List[ModelFit], y: Sequence[float]) -> ModelFit:
    return min(candidates, key=lambda fit: _sse(y, fit.fitted))


# ─────────────────────────────────────────────
# Benchmarks
# ─────────────────────────────────────────────

def naive(y: Sequence[float], h: int) -> ModelFit:
    fitted = [math.nan] + list(y[:-1])
    return ModelFit("Naive", fitted, _clip([y[-1]] * h), smoothing=1.0)


def seasonal_naive(y: Sequence[float], h: int, m: int = SEASON) -> ModelFit:
    fitted = [math.nan] * m + list(y[:-m])
    last_cycle = list(y[-m:])
    forecast = [last_cycle[k % m] for k in range(h)]
    return ModelFit("Seasonal Naive", fitted, _clip(forecast), {"season": m}, smoothing=1.0)


def moving_average(y: Sequence[float], h: int, window: Optional[int] = None) -> ModelFit:
    if window is None:
        windows = [w for w in (7, 14, 28) if w < len(y)] or [max(1, len(y) - 1)]
        return _best([moving_average(y, h, w) for w in windows], y)
    fitted = [math.nan] * len(y)
    running = sum(y[:window])
    for t in range(window, len(y)):
        fitted[t] = running / window
        running += y[t] - y[t - window]
    level = sum(y[-window:]) / window
    return ModelFit("Moving Average", fitted, _clip([level] * h), {"window": window},
                    smoothing=1 / window)


# ─────────────────────────────────────────────
# Exponential smoothing family
# ─────────────────────────────────────────────

def ses(y: Sequence[float], h: int, alpha: Optional[float] = None) -> ModelFit:
    """Simple exponential smoothing: level only."""
    if alpha is None:
        return _best([ses(y, h, a) for a in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9)], y)
    level = y[0]
    fitted = [math.nan]
    for value in y[1:]:
        fitted.append(level)
        level += alpha * (value - level)
    return ModelFit("SES", fitted, _clip([level] * h), {"alpha": alpha}, smoothing=alpha)


def holt(
    y: Sequence[float],
    h: int,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    phi: Optional[float] = None,
) -> ModelFit:
    """Holt's linear trend with damping (phi < 1 flattens the trend over the horizon)."""
    if alpha is None or beta is None or phi is None:
        grid = itertools.product((0.1, 0.2, 0.3, 0.5, 0.8), (0.01, 0.05, 0.1, 0.2), (0.9, 0.98))
        return _best([holt(y, h, a, b, p) for a, b, p in grid], y)
    level, trend = y[0], y[1] - y[0]
    fitted = [math.nan]
    for value in y[1:]:
        fitted.append(level + phi * trend)
        new_level = alpha * value + (1 - alpha) * (level + phi * trend)
        trend = beta * (new_level - level) + (1 - beta) * phi * trend
        level = new_level
    forecast = []
    damp = 0.0
    for k in range(1, h + 1):
        damp += phi ** k
        forecast.append(level + damp * trend)
    params = {"alpha": alpha, "beta": beta, "phi": phi}
    return ModelFit("Holt (damped)", fitted, _clip(forecast), params, smoothing=alpha)


def holt_winters(
    y: Sequence[float],
    h: int,
    alpha: Optional[float] = None,
    beta: Optional[float] = None,
    gamma: Optional[float] = None,
    m: int = SEASON,
) -> ModelFit:
    """Additive Holt-Winters: level + trend + weekly seasonal component."""
    if alpha is None or beta is None or gamma is None:
        grid = itertools.product((0.05, 0.1, 0.2, 0.4), (0.0, 0.02, 0.05), (0.05, 0.1, 0.3))
        return _best([holt_winters(y, h, a, b, g, m) for a, b, g in grid], y)
    first, second = sum(y[:m]) / m, sum(y[m:2 * m]) / m
    level, trend = first, (second - first) / m
    season = [y[i] - first for i in range(m)]
    fitted = [math.nan] * m
    for t in range(m, len(y)):
        s = season[t - m]
        fitted.append(level + trend + s)
        new_level = alpha * (y[t] - s) + (1 - alpha) * (level + trend)
        trend = beta * (new_level - level) + (1 - beta) * trend
        season.append(gamma * (y[t] - new_level) + (1 - gamma) * s)
        level = new_level
    n = len(y)
    forecast = [level + k * trend + season[n - m + (k - 1) % m] for k in range(1, h + 1)]
    params = {"alpha": alpha, "beta": beta, "gamma": gamma, "season": m}
    return ModelFit("Holt-Winters", fitted, _clip(forecast), params, smoothing=alpha)


# ─────────────────────────────────────────────
# Intermittent demand
# ─────────────────────────────────────────────

def _croston_core(y: Sequence[float], alpha: float) -> Tuple[List[float], float]:
    """Smooths non-zero demand size and the interval between demands separately."""
    size: Optional[float] = None
    interval = 1.0
    periods_since = 0
    fitted = []
    for value in y:
        fitted.append(size / interval if size is not None else math.nan)
        periods_since += 1
        if value > 0:
            if size is None:
                size, interval = float(value), float(periods_since)
            else:
                size += alpha * (value - size)
                interval += alpha * (periods_since - interval)
            periods_since = 0
    return fitted, (size / interval if size is not None else 0.0)


def croston(y: Sequence[float], h: int, alpha: Optional[float] = None) -> ModelFit:
    if alpha is None:
        return _best([croston(y, h, a) for a in (0.05, 0.1, 0.2, 0.3)], y)
    fitted, rate = _croston_core(y, alpha)
    return ModelFit("Croston", fitted, [rate] * h, {"alpha": alpha}, smoothing=alpha)


def sba(y: Sequence[float], h: int, alpha: Optional[float] = None) -> ModelFit:
    """Syntetos-Boylan approximation: Croston with a (1 - alpha/2) bias correction."""
    if alpha is None:
        return _best([sba(y, h, a) for a in (0.05, 0.1, 0.2, 0.3)], y)
    fitted, rate = _croston_core(y, alpha)
    k = 1 - alpha / 2
    fitted = [f * k for f in fitted]
    return ModelFit("Croston-SBA", fitted, [rate * k] * h, {"alpha": alpha}, smoothing=alpha)


def tsb(
    y: Sequence[float], h: int, alpha: Optional[float] = None, beta: Optional[float] = None
) -> ModelFit:
    """Teunter-Syntetos-Babai: smooths demand probability every period, so it decays
    towards zero when an item stops selling (Croston never updates without a sale)."""
    if alpha is None or beta is None:
        grid = itertools.product((0.05, 0.1, 0.2, 0.3), (0.05, 0.1, 0.2, 0.3))
        return _best([tsb(y, h, a, b) for a, b in grid], y)
    nonzero = [v for v in y if v > 0]
    prob = len(nonzero) / len(y)
    size = sum(nonzero) / len(nonzero) if nonzero else 0.0
    fitted = []
    for value in y:
        fitted.append(prob * size)
        if value > 0:
            prob += alpha * (1 - prob)
            size += beta * (value - size)
        else:
            prob -= alpha * prob
    params = {"alpha": alpha, "beta": beta}
    return ModelFit("TSB", fitted, [prob * size] * h, params, smoothing=alpha)


ModelFn = Callable[[Sequence[float], int], ModelFit]

# (model, minimum history length)
SMOOTH_MODELS: List[Tuple[ModelFn, int]] = [
    (naive, 2),
    (seasonal_naive, SEASON + 1),
    (moving_average, 8),
    (ses, 3),
    (holt, 4),
    (holt_winters, 2 * SEASON + 2),
]
INTERMITTENT_MODELS: List[Tuple[ModelFn, int]] = [
    (croston, 3),
    (sba, 3),
    (tsb, 3),
    (moving_average, 8),
    (ses, 3),
]
