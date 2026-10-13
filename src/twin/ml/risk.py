import math
from dataclasses import dataclass

import numpy as np

from twin.common.metrics import Threshold


def normal_cdf(x: np.ndarray | float) -> np.ndarray:
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, dtype=float) / math.sqrt(2.0)))


def to_model_threshold(threshold: Threshold) -> Threshold:
    if not threshold.log_scale:
        return threshold
    return Threshold(math.log10(threshold.warn), math.log10(threshold.crit), threshold.direction, log_scale=False)


def crossing_probability(mean: np.ndarray, std: np.ndarray, limit: float, direction: str) -> np.ndarray:
    z = (limit - mean) / np.maximum(std, 1e-9)
    if direction == "high":
        return 1.0 - normal_cdf(z)
    return normal_cdf(z)


def rate_of_change(history: np.ndarray, step_s: float, lookback: int = 10) -> float:
    recent = np.asarray(history[-lookback:], dtype=float)
    if len(recent) < 2:
        return 0.0
    slope_per_step = np.polyfit(np.arange(len(recent)), recent, 1)[0]
    return float(slope_per_step * 3600.0 / step_s)


def residual_zscore(actual: float, predicted: float, std: float) -> float:
    return float((actual - predicted) / max(std, 1e-9))


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    severity: str
    p_warn: float
    p_crit: float
    rate_per_hour: float
    z_score: float
    breach_step: int | None
    current_severity: str | None


def severity_for(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.5:
        return "warning"
    return "ok"


def assess(
    history: np.ndarray,
    forecast_mean: np.ndarray,
    forecast_std: np.ndarray,
    threshold: Threshold,
    step_s: float,
    last_residual_z: float = 0.0,
) -> RiskAssessment:
    p_warn = crossing_probability(forecast_mean, forecast_std, threshold.warn, threshold.direction)
    p_crit = crossing_probability(forecast_mean, forecast_std, threshold.crit, threshold.direction)
    rate = rate_of_change(history, step_s)
    toward_limit = rate if threshold.direction == "high" else -rate
    span = max(abs(threshold.crit - threshold.warn), 1e-9)
    rate_term = float(np.clip(toward_limit / (2.0 * span), 0.0, 1.0))
    z_term = float(np.clip((abs(last_residual_z) - 2.0) / 4.0, 0.0, 1.0))
    base = max(float(p_crit.max()), 0.75 * float(p_warn.max()))
    score = float(np.clip(base + 0.15 * rate_term + 0.10 * z_term, 0.0, 1.0))
    breaching = np.nonzero(p_warn >= 0.5)[0]
    return RiskAssessment(
        score=score,
        severity=severity_for(score),
        p_warn=float(p_warn.max()),
        p_crit=float(p_crit.max()),
        rate_per_hour=rate,
        z_score=last_residual_z,
        breach_step=int(breaching[0]) + 1 if len(breaching) else None,
        current_severity=threshold.breached(float(history[-1])),
    )
