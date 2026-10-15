from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from twin.common.topology import device_type_of
from twin.ml.tasks import ForecastTask, WindowConfig
from twin.ml.transform import to_model_space
from twin.ml.windows import StandardScaler, chronological_split, sliding_windows


def load_csv(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"device_key": "string", "metric": "string"})
    frame["ts"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
    return frame


def load_postgres(dsn: str, since: str | None = None, until: str | None = None) -> pd.DataFrame:
    from sqlalchemy import create_engine, text

    query = "SELECT bucket AS ts, device_key, metric, avg_value AS value FROM telemetry_1m WHERE true"
    params: dict[str, str] = {}
    if since:
        query += " AND bucket >= :since"
        params["since"] = since
    if until:
        query += " AND bucket < :until"
        params["until"] = until
    engine = create_engine(dsn)
    with engine.connect() as conn:
        return pd.read_sql(text(query + " ORDER BY bucket"), conn, params=params, parse_dates=["ts"])


def device_frames(long_frame: pd.DataFrame, task: ForecastTask, step_s: int = 60) -> dict[str, pd.DataFrame]:
    wanted = long_frame[long_frame["metric"].isin(task.features)]
    keys = [key for key in wanted["device_key"].unique() if device_type_of(str(key)) == task.device_type]
    wanted = wanted[wanted["device_key"].isin(keys)]
    wide = wanted.pivot_table(index=["device_key", "ts"], columns="metric", values="value", aggfunc="mean")
    frames: dict[str, pd.DataFrame] = {}
    for key, group in wide.groupby(level="device_key"):
        series = group.droplevel("device_key").sort_index()
        series = series.resample(f"{step_s}s").mean().ffill(limit=3).dropna()
        if set(task.features) <= set(series.columns):
            frames[str(key)] = series[list(task.features)]
    return frames


@dataclass
class TaskData:
    task: ForecastTask
    window: WindowConfig
    scaler: StandardScaler
    x_train: np.ndarray
    y_train: np.ndarray
    x_val: np.ndarray
    y_val: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    test_segments: dict[str, np.ndarray]


def build_task_data(
    frames: dict[str, pd.DataFrame],
    task: ForecastTask,
    window: WindowConfig,
    val_fraction: float = 0.15,
    test_fraction: float = 0.15,
) -> TaskData:
    splits: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for key, frame in frames.items():
        values = to_model_space(frame[list(task.features)].to_numpy(), task)
        train_slice, val_slice, test_slice = chronological_split(len(values), val_fraction, test_fraction)
        splits[key] = (values[train_slice], values[val_slice], values[test_slice])
    if not splits:
        raise ValueError(f"no usable devices for task {task.name}")
    scaler = StandardScaler.fit(np.concatenate([train for train, _, _ in splits.values()]))
    buckets: list[list[np.ndarray]] = [[], [], [], [], [], []]
    for train, val, test in splits.values():
        for position, segment in enumerate((train, val, test)):
            inputs, outputs = sliding_windows(
                scaler.transform(segment),
                window.input_len,
                window.horizon,
                task.target_index,
                window.stride,
            )
            if len(inputs):
                buckets[position * 2].append(inputs)
                buckets[position * 2 + 1].append(outputs)
    arrays = [np.concatenate(parts) if parts else np.empty((0,)) for parts in buckets]
    return TaskData(
        task,
        window,
        scaler,
        *arrays,
        test_segments={key: parts[2] for key, parts in splits.items()},
    )
