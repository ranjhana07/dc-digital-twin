import numpy as np
import pytest

pd = pytest.importorskip("pandas")

from twin.ml.dataset import build_task_data, device_frames
from twin.ml.tasks import TASKS, WindowConfig
from twin.simulator.engine import Simulation
from twin.common.topology import build_topology

T0 = 1_780_000_000.0


@pytest.fixture(scope="module")
def long_frame():
    topology = build_topology(halls=1, racks_per_hall=2, servers_per_rack=2, xcvrs_per_switch=1)
    simulation = Simulation(topology, seed=4)
    rows = []
    for index in range(240):
        for reading in simulation.step(T0 + index * 60, 60):
            rows.append((reading.ts, reading.device_key, reading.metric, reading.value))
    frame = pd.DataFrame(rows, columns=["ts", "device_key", "metric", "value"])
    frame["ts"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
    return frame


def test_device_frames_filter_by_device_type(long_frame):
    frames = device_frames(long_frame, TASKS["thermal"], step_s=60)
    assert sorted(frames) == [
        "dc1/hall-a/r01/srv-01",
        "dc1/hall-a/r01/srv-02",
        "dc1/hall-a/r02/srv-01",
        "dc1/hall-a/r02/srv-02",
    ]
    assert list(frames["dc1/hall-a/r01/srv-01"].columns) == list(TASKS["thermal"].features)
    assert len(frames["dc1/hall-a/r01/srv-01"]) == 240


def test_build_task_data_shapes_and_scaling(long_frame):
    task = TASKS["thermal"]
    window = WindowConfig(input_len=20, horizon=5, stride=3)
    data = build_task_data(device_frames(long_frame, task), task, window)
    assert data.x_train.shape[1:] == (20, 5)
    assert data.y_train.shape[1:] == (5, 2)
    assert len(data.x_train) > len(data.x_val) > 0
    assert len(data.x_test) > 0
    assert abs(float(data.x_train[..., 0].mean())) < 1.0


def test_ber_task_uses_log_space(long_frame):
    task = TASKS["ber"]
    window = WindowConfig(input_len=20, horizon=5, stride=3)
    data = build_task_data(device_frames(long_frame, task), task, window)
    raw_ber_index = task.features.index("pre_fec_ber")
    assert abs(data.scaler.mean[raw_ber_index]) > 5
    assert np.isfinite(data.x_train).all()
