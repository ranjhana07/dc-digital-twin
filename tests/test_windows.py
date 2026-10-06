import numpy as np
import pytest

from twin.ml.windows import StandardScaler, chronological_split, latest_window, sliding_windows


def ramp(steps=20, features=3):
    return np.arange(steps * features, dtype=float).reshape(steps, features)


def test_window_shapes_and_alignment():
    values = ramp()
    inputs, outputs = sliding_windows(values, input_len=5, horizon=3, target_index=[0, 2])
    assert inputs.shape == (13, 5, 3)
    assert outputs.shape == (13, 3, 2)
    np.testing.assert_array_equal(inputs[0], values[0:5])
    np.testing.assert_array_equal(outputs[0], values[5:8][:, [0, 2]])
    np.testing.assert_array_equal(outputs[-1], values[17:20][:, [0, 2]])


def test_stride_skips_windows():
    inputs, _ = sliding_windows(ramp(), 5, 3, [0], stride=4)
    assert len(inputs) == 4
    np.testing.assert_array_equal(inputs[1][0], ramp()[4])


def test_series_shorter_than_window_is_empty():
    inputs, outputs = sliding_windows(ramp(steps=6), 5, 3, [0])
    assert inputs.shape[0] == 0 and outputs.shape[0] == 0


def test_scaler_roundtrip_and_serialisation():
    values = ramp(50) * [1.0, 5.0, 0.1]
    scaler = StandardScaler.fit(values)
    scaled = scaler.transform(values)
    np.testing.assert_allclose(scaled.mean(axis=0), 0.0, atol=1e-9)
    np.testing.assert_allclose(scaled.std(axis=0), 1.0, atol=1e-9)
    restored = StandardScaler.from_dict(scaler.to_dict())
    np.testing.assert_allclose(restored.inverse_targets(scaled[:, [0, 2]], [0, 2]), values[:, [0, 2]])


def test_constant_feature_does_not_divide_by_zero():
    values = np.ones((10, 2))
    scaler = StandardScaler.fit(values)
    assert np.isfinite(scaler.transform(values)).all()


def test_chronological_split_has_no_overlap():
    train, val, test = chronological_split(100, 0.15, 0.15)
    assert (train.stop, val.start, val.stop, test.start, test.stop) == (70, 70, 85, 85, 100)


def test_latest_window():
    values = ramp(10)
    np.testing.assert_array_equal(latest_window(values, 4), values[-4:])
    with pytest.raises(ValueError):
        latest_window(values, 11)
