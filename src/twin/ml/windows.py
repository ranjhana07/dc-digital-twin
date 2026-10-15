from dataclasses import dataclass

import numpy as np


@dataclass
class StandardScaler:
    mean: np.ndarray
    std: np.ndarray

    @classmethod
    def fit(cls, values: np.ndarray, eps: float = 1e-6) -> "StandardScaler":
        flat = values.reshape(-1, values.shape[-1])
        return cls(flat.mean(axis=0), np.maximum(flat.std(axis=0), eps))

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (values - self.mean) / self.std

    def inverse_targets(self, values: np.ndarray, target_index: list[int]) -> np.ndarray:
        return values * self.std[target_index] + self.mean[target_index]

    def to_dict(self) -> dict[str, list[float]]:
        return {"mean": self.mean.tolist(), "std": self.std.tolist()}

    @classmethod
    def from_dict(cls, data: dict[str, list[float]]) -> "StandardScaler":
        return cls(np.asarray(data["mean"], dtype=np.float64), np.asarray(data["std"], dtype=np.float64))


def sliding_windows(
    values: np.ndarray, input_len: int, horizon: int, target_index: list[int], stride: int = 1
) -> tuple[np.ndarray, np.ndarray]:
    steps, features = values.shape
    last_start = steps - input_len - horizon
    if last_start < 0:
        return np.empty((0, input_len, features)), np.empty((0, horizon, len(target_index)))
    starts = np.arange(0, last_start + 1, stride)
    inputs = np.stack([values[start : start + input_len] for start in starts])
    outputs = np.stack(
        [values[start + input_len : start + input_len + horizon][:, target_index] for start in starts]
    )
    return inputs, outputs


def latest_window(values: np.ndarray, input_len: int) -> np.ndarray:
    if len(values) < input_len:
        raise ValueError(f"need {input_len} steps, got {len(values)}")
    return values[-input_len:]


def chronological_split(length: int, val_fraction: float, test_fraction: float) -> tuple[slice, slice, slice]:
    test_start = int(length * (1.0 - test_fraction))
    val_start = int(length * (1.0 - test_fraction - val_fraction))
    return slice(0, val_start), slice(val_start, test_start), slice(test_start, length)
