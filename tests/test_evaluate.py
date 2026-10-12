import numpy as np
import pytest

from twin.ml.evaluate import mape, per_horizon_metrics, persistence_forecast, residual_std, summarize


def test_metrics_per_horizon():
    y_true = np.array([[[1.0], [2.0]], [[3.0], [4.0]]])
    y_pred = np.array([[[2.0], [2.0]], [[3.0], [6.0]]])
    result = per_horizon_metrics(y_true, y_pred, ("temp",))
    assert result["temp"]["mae"] == pytest.approx([0.5, 1.0])
    assert result["temp"]["rmse"] == pytest.approx([np.sqrt(0.5), np.sqrt(2.0)])
    assert result["temp"]["mape"] == pytest.approx([100 * (1 / 1 + 0) / 2, 100 * (0 + 2 / 4) / 2])
    assert summarize(result)["temp"]["mae"] == pytest.approx(0.75)


def test_shape_mismatch_raises():
    with pytest.raises(ValueError):
        per_horizon_metrics(np.zeros((2, 3, 1)), np.zeros((2, 4, 1)), ("x",))


def test_mape_handles_zero_targets():
    assert np.isfinite(mape(np.zeros((2, 3)), np.ones((2, 3)))).all()


def test_persistence_repeats_last_target():
    x = np.arange(2 * 4 * 3, dtype=float).reshape(2, 4, 3)
    forecast = persistence_forecast(x, [0, 2], horizon=5)
    assert forecast.shape == (2, 5, 2)
    assert (forecast[0, :, 0] == x[0, -1, 0]).all()
    assert (forecast[1, :, 1] == x[1, -1, 2]).all()


def test_residual_std_shape():
    rng = np.random.default_rng(0)
    truth = rng.normal(size=(50, 6, 2))
    assert residual_std(truth, truth + rng.normal(scale=0.3, size=truth.shape)).shape == (6, 2)
