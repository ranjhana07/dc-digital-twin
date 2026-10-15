import numpy as np
import pytest

from twin.ml.inference import AlertSpec, InferenceService, TaskBundle, assemble_windows
from twin.ml.tasks import TASKS, WindowConfig
from twin.ml.windows import StandardScaler

NOW = 1_780_000_000.0
SERVER = "dc1/hall-a/r01/srv-01"


def rows_for(task, device_key, values, start=NOW - 3600, step=60):
    rows = []
    for index, row in enumerate(values):
        for name, value in zip(task.features, row):
            rows.append((device_key, name, start + index * step, float(value)))
    return rows


def thermal_values(length, inlet_end):
    inlet = np.linspace(22.0, inlet_end, length)
    return np.column_stack([inlet, inlet + 10, np.full(length, 0.5), np.full(length, 5000.0), np.full(length, 300.0)])


class FakeStore:
    def __init__(self, rows):
        self.rows = rows
        self.predictions, self.risks, self.opened, self.resolved = [], [], [], []

    def metric_rows(self, task, since_epoch):
        return [row for row in self.rows if row[2] >= since_epoch]

    def write_predictions(self, rows):
        self.predictions.extend(rows)

    def upsert_risk(self, rows):
        self.risks.extend(rows)

    def open_alert(self, spec: AlertSpec):
        self.opened.append(spec)

    def resolve_alerts(self, device_key, metric, keep_kind):
        self.resolved.append((device_key, metric, keep_kind))


def make_bundle(slope_per_step):
    task = TASKS["thermal"]
    window = WindowConfig(input_len=20, horizon=10, step_s=60)
    scaler = StandardScaler(np.zeros(5), np.ones(5))
    residual = np.full((10, 2), 0.5)

    def forecast(batch):
        last = batch[:, -1][:, task.target_index]
        steps = np.arange(1, 11)[None, :, None]
        return last[:, None, :] + slope_per_step * steps

    return TaskBundle(task, window, scaler, residual, "test", forecast)


def test_assemble_windows_requires_all_features_and_length():
    task = TASKS["thermal"]
    rows = rows_for(task, SERVER, thermal_values(25, 24.0))
    windows = assemble_windows(rows, task, 21)
    matrix, last_bucket = windows[SERVER]
    assert matrix.shape == (21, 5)
    assert last_bucket == NOW - 3600 + 24 * 60
    assert assemble_windows(rows, task, 30) == {}
    assert assemble_windows([row for row in rows if row[1] != "fan_rpm"], task, 21) == {}
    assert assemble_windows(rows_for(task, "dc1/hall-a/r01/pdu-a", thermal_values(25, 24.0)), task, 21) == {}


def test_quiet_series_writes_predictions_and_no_alert():
    task = TASKS["thermal"]
    store = FakeStore(rows_for(task, SERVER, thermal_values(25, 23.0), start=NOW - 24 * 60))
    summary = InferenceService({"thermal": make_bundle(0.0)}, store).run_once(NOW)
    assert summary == {"devices": 1, "alerts": 0}
    assert len(store.predictions) == 2 * 10
    assert {row[1] for row in store.predictions} == {"inlet_temp", "outlet_temp"}
    assert all(row[7] <= row[6] <= row[8] for row in store.predictions)
    assert store.opened == []
    assert (SERVER, "inlet_temp", None) in store.resolved


def test_rising_forecast_opens_forecast_alert():
    task = TASKS["thermal"]
    store = FakeStore(rows_for(task, SERVER, thermal_values(25, 25.0), start=NOW - 24 * 60))
    InferenceService({"thermal": make_bundle(0.8)}, store).run_once(NOW)
    inlet_alerts = [spec for spec in store.opened if spec.metric == "inlet_temp"]
    assert len(inlet_alerts) == 1
    assert inlet_alerts[0].kind == "forecast"
    assert inlet_alerts[0].rack_key == "dc1/hall-a/r01"
    assert inlet_alerts[0].risk_score >= 0.5


def test_current_breach_opens_threshold_alert():
    task = TASKS["thermal"]
    store = FakeStore(rows_for(task, SERVER, thermal_values(25, 33.0), start=NOW - 24 * 60))
    InferenceService({"thermal": make_bundle(0.0)}, store).run_once(NOW)
    spec = next(spec for spec in store.opened if spec.metric == "inlet_temp")
    assert spec.kind == "threshold"
    assert spec.severity == "critical"
