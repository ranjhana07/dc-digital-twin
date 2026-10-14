import logging
import time
from collections import defaultdict
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from twin.common.metrics import threshold_for
from twin.common.topology import device_type_of, rack_key_of
from twin.ml.risk import RiskAssessment, assess, residual_zscore, to_model_threshold
from twin.ml.tasks import ForecastTask, WindowConfig
from twin.ml.transform import from_model_space, to_model_space
from twin.ml.windows import StandardScaler

log = logging.getLogger("twin.inference")

Z_BAND = 1.96


@dataclass
class TaskBundle:
    task: ForecastTask
    window: WindowConfig
    scaler: StandardScaler
    residual_std: np.ndarray
    version: str
    forecast: Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class AlertSpec:
    device_key: str
    rack_key: str
    metric: str
    kind: str
    severity: str
    message: str
    risk_score: float


class ForecastStore(Protocol):
    def metric_rows(self, task: ForecastTask, since_epoch: float) -> list[tuple[str, str, float, float]]: ...

    def write_predictions(self, rows: list[tuple]) -> None: ...

    def upsert_risk(self, rows: list[tuple]) -> None: ...

    def open_alert(self, spec: AlertSpec) -> None: ...

    def resolve_alerts(self, device_key: str, metric: str, keep_kind: str | None) -> None: ...


def bundle_from_checkpoint(path: Path) -> TaskBundle:
    import torch

    from twin.ml.checkpoint import load_checkpoint

    loaded = load_checkpoint(path)

    def forecast(batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return loaded.model(torch.from_numpy(batch).float()).numpy()

    return TaskBundle(loaded.task, loaded.window, loaded.scaler, loaded.residual_std, loaded.version, forecast)


def assemble_windows(
    rows: Sequence[tuple[str, str, float, float]], task: ForecastTask, length: int
) -> dict[str, tuple[np.ndarray, float]]:
    series: dict[str, dict[str, dict[float, float]]] = defaultdict(lambda: defaultdict(dict))
    for device_key, metric, bucket, value in rows:
        if metric in task.features and device_type_of(device_key) == task.device_type:
            series[device_key][metric][bucket] = value
    windows: dict[str, tuple[np.ndarray, float]] = {}
    for device_key, by_metric in series.items():
        if len(by_metric) != len(task.features):
            continue
        shared = sorted(set.intersection(*(set(buckets) for buckets in by_metric.values())))
        if len(shared) < length:
            continue
        chosen = shared[-length:]
        matrix = np.array([[by_metric[name][bucket] for name in task.features] for bucket in chosen])
        windows[device_key] = (matrix, chosen[-1])
    return windows


class InferenceService:
    def __init__(self, bundles: dict[str, TaskBundle], store: ForecastStore, alert_min_score: float = 0.5) -> None:
        self.bundles = bundles
        self.store = store
        self.alert_min_score = alert_min_score

    def run_once(self, now_epoch: float | None = None) -> dict[str, int]:
        now_epoch = now_epoch or time.time()
        summary = {"devices": 0, "alerts": 0}
        for name, bundle in self.bundles.items():
            window = bundle.window
            lookback = (window.input_len + 3) * window.step_s
            rows = self.store.metric_rows(bundle.task, now_epoch - lookback)
            windows = assemble_windows(rows, bundle.task, window.input_len + 1)
            prediction_rows, risk_rows = [], []
            for device_key, (matrix, last_bucket) in windows.items():
                results = self.forecast_device(bundle, device_key, matrix, last_bucket)
                for target, assessment, predicted, lower, upper in results:
                    risk_rows.append(self.risk_row(name, device_key, target, assessment, now_epoch))
                    prediction_rows.extend(
                        self.prediction_rows(bundle, device_key, target, predicted, lower, upper, last_bucket, now_epoch)
                    )
                    summary["alerts"] += self.sync_alert(device_key, target, assessment)
                summary["devices"] += 1
            if prediction_rows:
                self.store.write_predictions(prediction_rows)
                self.store.upsert_risk(risk_rows)
        return summary

    def forecast_device(self, bundle: TaskBundle, device_key: str, matrix: np.ndarray, last_bucket: float) -> list[tuple]:
        task, window = bundle.task, bundle.window
        model_space = to_model_space(matrix, task)
        scaled = bundle.scaler.transform(model_space)
        batch = np.stack([scaled[:-1], scaled[1:]])
        output = bundle.scaler.inverse_targets(bundle.forecast(batch), task.target_index)
        previous_first_step, latest_forecast = output[0, 0], output[1]
        results = []
        for position, target in enumerate(task.targets):
            feature_index = task.features.index(target)
            history = model_space[1:, feature_index]
            std = bundle.residual_std[:, position]
            z = residual_zscore(history[-1], previous_first_step[position], std[0])
            threshold = threshold_for(device_type_of(device_key), target)
            mean = latest_forecast[:, position]
            if threshold is None:
                continue
            assessment = assess(history, mean, std, to_model_threshold(threshold), window.step_s, z)
            lower, upper = mean - Z_BAND * std, mean + Z_BAND * std
            results.append((target, assessment, mean, lower, upper))
        return results

    def prediction_rows(self, bundle, device_key, target, mean, lower, upper, last_bucket, now_epoch) -> list[tuple]:
        task, step_s = bundle.task, bundle.window.step_s

        def as_raw(values: np.ndarray) -> np.ndarray:
            return from_model_space(values.reshape(-1, 1), task, (target,)).ravel()

        mean_raw, lower_raw, upper_raw = as_raw(mean), as_raw(lower), as_raw(upper)
        return [
            (
                device_key,
                target,
                task.name,
                now_epoch,
                last_bucket + (step + 1) * step_s,
                step + 1,
                float(mean_raw[step]),
                float(min(lower_raw[step], upper_raw[step])),
                float(max(lower_raw[step], upper_raw[step])),
                bundle.version,
            )
            for step in range(len(mean))
        ]

    @staticmethod
    def risk_row(task_name: str, device_key: str, target: str, assessment: RiskAssessment, now_epoch: float) -> tuple:
        return (
            device_key,
            target,
            task_name,
            now_epoch,
            assessment.score,
            assessment.severity,
            assessment.p_warn,
            assessment.p_crit,
            assessment.rate_per_hour,
            assessment.z_score,
            assessment.breach_step,
        )

    def sync_alert(self, device_key: str, metric: str, assessment: RiskAssessment) -> int:
        rack_key = rack_key_of(device_key)
        if assessment.current_severity:
            spec = AlertSpec(
                device_key,
                rack_key,
                metric,
                "threshold",
                assessment.current_severity,
                f"{metric} is past its {assessment.current_severity} threshold",
                assessment.score,
            )
        elif assessment.score >= self.alert_min_score:
            when = f" in about {assessment.breach_step} min" if assessment.breach_step else ""
            spec = AlertSpec(
                device_key,
                rack_key,
                metric,
                "forecast",
                "critical" if assessment.severity == "critical" else "warning",
                f"{metric} is forecast to cross its threshold{when}",
                assessment.score,
            )
        else:
            self.store.resolve_alerts(device_key, metric, None)
            return 0
        self.store.resolve_alerts(device_key, metric, spec.kind)
        self.store.open_alert(spec)
        return 1
