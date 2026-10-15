import numpy as np
import pytest

torch = pytest.importorskip("torch")
pd = pytest.importorskip("pandas")

from twin.ml.checkpoint import load_checkpoint
from twin.ml.dataset import build_task_data
from twin.ml.evaluate import predict
from twin.ml.tasks import TASKS, WindowConfig
from twin.ml.train import TrainConfig, evaluate_model, fit, train_task


def synthetic_frames(task, devices=3, steps=400):
    rng = np.random.default_rng(1)
    index = pd.date_range("2026-01-01", periods=steps, freq="60s", tz="UTC")
    frames = {}
    for device in range(devices):
        phase = rng.uniform(0, 6)
        base = np.sin(np.arange(steps) / 25.0 + phase)
        columns = {name: base * (position + 1) + rng.normal(scale=0.05, size=steps) + 10 for position, name in enumerate(task.features)}
        if "pre_fec_ber" in columns:
            columns["pre_fec_ber"] = 10 ** (-9 + 0.5 * base)
        frames[f"dc1/hall-a/r01/dev-{device}"] = pd.DataFrame(columns, index=index)
    return frames


@pytest.fixture(scope="module")
def data():
    task = TASKS["thermal"]
    return build_task_data(synthetic_frames(task), task, WindowConfig(input_len=24, horizon=6, stride=2))


def test_training_reduces_validation_loss(data):
    config = TrainConfig(hidden_size=16, num_layers=1, max_epochs=6, patience=6)
    model, history = fit(data, config)
    assert len(history) >= 2
    assert history[-1]["val_loss"] < history[0]["val_loss"]
    assert predict(model, data.x_test).shape == data.y_test.shape


def test_evaluation_reports_baseline(data):
    model, _ = fit(data, TrainConfig(hidden_size=16, num_layers=1, max_epochs=3))
    report = evaluate_model(model, data)
    assert set(report["gru_summary"]) == set(data.task.targets)
    assert len(report["gru"]["inlet_temp"]["mae"]) == 6
    assert report["persistence_summary"]["inlet_temp"]["mae"] > 0


def test_checkpoint_roundtrip(tmp_path, data):
    path = train_task(data, TrainConfig(hidden_size=16, num_layers=1, max_epochs=2), tmp_path)
    loaded = load_checkpoint(path)
    assert loaded.task.name == "thermal"
    assert loaded.window.horizon == 6
    assert loaded.residual_std.shape == (6, 2)
    sample = data.x_test[:4]
    np.testing.assert_allclose(predict(loaded.model, sample), predict(loaded.model, sample), atol=1e-6)
    assert path.with_suffix(".metrics.json").exists()
