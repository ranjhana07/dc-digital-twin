from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from twin.ml.models import GRUForecaster
from twin.ml.tasks import TASKS, ForecastTask, WindowConfig
from twin.ml.windows import StandardScaler

FORMAT_VERSION = 1


@dataclass
class LoadedModel:
    model: GRUForecaster
    task: ForecastTask
    window: WindowConfig
    scaler: StandardScaler
    residual_std: np.ndarray
    metrics: dict
    version: str


def save_checkpoint(
    path: Path,
    model: GRUForecaster,
    task: ForecastTask,
    window: WindowConfig,
    scaler: StandardScaler,
    residual_std: np.ndarray,
    metrics: dict,
    hyper: dict,
    version: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "format": FORMAT_VERSION,
            "task": task.name,
            "state_dict": model.state_dict(),
            "hyper": hyper,
            "window": {
                "input_len": window.input_len,
                "horizon": window.horizon,
                "step_s": window.step_s,
                "stride": window.stride,
            },
            "scaler": scaler.to_dict(),
            "residual_std": residual_std.tolist(),
            "metrics": metrics,
            "version": version,
        },
        path,
    )


def load_checkpoint(path: Path) -> LoadedModel:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    task = TASKS[payload["task"]]
    window = WindowConfig(**payload["window"])
    hyper = payload["hyper"]
    model = GRUForecaster(
        n_features=len(task.features),
        target_index=task.target_index,
        horizon=window.horizon,
        hidden_size=hyper["hidden_size"],
        num_layers=hyper["num_layers"],
        dropout=hyper["dropout"],
    )
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return LoadedModel(
        model=model,
        task=task,
        window=window,
        scaler=StandardScaler.from_dict(payload["scaler"]),
        residual_std=np.asarray(payload["residual_std"]),
        metrics=payload["metrics"],
        version=payload["version"],
    )
