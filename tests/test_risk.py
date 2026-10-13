import math

import numpy as np
import pytest

from twin.common.metrics import Threshold
from twin.ml.risk import assess, crossing_probability, normal_cdf, rate_of_change, residual_zscore, to_model_threshold

HIGH = Threshold(warn=27.0, crit=32.0)
LOW = Threshold(warn=-7.0, crit=-9.5, direction="low")


def test_normal_cdf_reference_points():
    assert normal_cdf(0.0) == pytest.approx(0.5)
    assert normal_cdf(1.96) == pytest.approx(0.975, abs=1e-3)


def test_crossing_probability_directions():
    mean = np.array([20.0, 27.0, 34.0])
    std = np.array([1.0, 1.0, 1.0])
    high = crossing_probability(mean, std, 27.0, "high")
    assert high[0] < 0.001 and high[1] == pytest.approx(0.5) and high[2] > 0.999
    low = crossing_probability(mean, std, 27.0, "low")
    assert low[0] > 0.999 and low[2] < 0.001


def test_rate_of_change_per_hour():
    history = np.arange(20, dtype=float) * 0.1
    assert rate_of_change(history, step_s=60.0) == pytest.approx(6.0)
    assert rate_of_change(np.array([5.0]), 60.0) == 0.0


def test_residual_zscore():
    assert residual_zscore(30.0, 27.0, 1.5) == pytest.approx(2.0)


def test_steady_series_far_from_limit_is_ok():
    history = np.full(30, 22.0)
    result = assess(history, np.full(10, 22.0), np.full(10, 0.5), HIGH, 60.0)
    assert result.severity == "ok"
    assert result.score < 0.05
    assert result.breach_step is None
    assert result.current_severity is None


def test_forecast_crossing_critical():
    history = np.linspace(24.0, 28.0, 30)
    forecast = np.linspace(28.5, 35.0, 10)
    result = assess(history, forecast, np.full(10, 1.0), HIGH, 60.0, last_residual_z=3.0)
    assert result.severity == "critical"
    assert result.p_crit > 0.9
    assert result.breach_step == 1
    assert result.current_severity == "warning"


def test_low_direction_threshold():
    history = np.linspace(-5.0, -6.5, 30)
    forecast = np.linspace(-6.6, -9.8, 10)
    result = assess(history, forecast, np.full(10, 0.4), LOW, 60.0)
    assert result.severity in ("warning", "critical")
    assert result.rate_per_hour < 0


def test_ber_threshold_moves_to_log_space():
    threshold = to_model_threshold(Threshold(1e-6, 1e-4, log_scale=True))
    assert threshold.warn == pytest.approx(-6.0)
    assert threshold.crit == pytest.approx(-4.0)
    assert not threshold.log_scale
    assert to_model_threshold(HIGH) is HIGH
