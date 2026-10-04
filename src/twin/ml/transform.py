import numpy as np

from twin.ml.tasks import ForecastTask

LOG_FLOOR = 1e-15


def to_model_space(values: np.ndarray, task: ForecastTask, names: tuple[str, ...] | None = None) -> np.ndarray:
    names = names or task.features
    out = np.array(values, dtype=np.float64, copy=True)
    for index, name in enumerate(names):
        if task.is_log(name):
            out[..., index] = np.log10(np.clip(out[..., index], LOG_FLOOR, None))
    return out


def from_model_space(values: np.ndarray, task: ForecastTask, names: tuple[str, ...] | None = None) -> np.ndarray:
    names = names or task.targets
    out = np.array(values, dtype=np.float64, copy=True)
    for index, name in enumerate(names):
        if task.is_log(name):
            out[..., index] = np.power(10.0, out[..., index])
    return out
