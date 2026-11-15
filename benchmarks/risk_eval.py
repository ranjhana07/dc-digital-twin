import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from twin.common.metrics import threshold_for
from twin.common.topology import Topology, build_topology, device_type_of
from twin.ml.checkpoint import load_checkpoint
from twin.ml.dataset import device_frames
from twin.ml.risk import assess, residual_zscore, to_model_threshold
from twin.ml.tasks import TASKS
from twin.ml.transform import to_model_space
from twin.simulator.engine import Simulation
from twin.simulator.faults import FaultKind, FaultSchedule, FaultSpec, random_schedule

EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
ACTIVE_INTENSITY = 0.3
ALERT_SCORE = 0.5


def epoch_seconds(index) -> np.ndarray:
    return np.asarray((index - EPOCH).total_seconds(), dtype=float)


def affected_series(spec: FaultSpec, topology: Topology) -> set[tuple[str, str]]:
    series: set[tuple[str, str]] = set()
    if spec.kind is FaultKind.COOLING_FAILURE:
        for rack_key in topology.sources_of(spec.target, "cooled_by"):
            for device in topology.devices_in_rack(rack_key):
                if device.type.value == "server":
                    series |= {(device.key, "inlet_temp"), (device.key, "outlet_temp")}
    elif spec.kind is FaultKind.FAN_DEGRADATION:
        series.add((spec.target, "outlet_temp"))
    elif spec.kind is FaultKind.DIRTY_OPTICS:
        series |= {(spec.target, "rx_power_dbm"), (spec.target, "pre_fec_ber")}
    elif spec.kind is FaultKind.PDU_OVERLOAD:
        series |= {(spec.target, "power_w"), (spec.target, "load_pct")}
        for device in topology.devices_in_rack(spec.target.rsplit("/", 1)[0]):
            if device.type.value == "server":
                series.add((device.key, "outlet_temp"))
    return series


def simulate(hours: float, seed: int, faults: int, racks: int, start: float) -> tuple[pd.DataFrame, FaultSchedule, Topology]:
    topology = build_topology(halls=1, racks_per_hall=racks)
    schedule = random_schedule(topology, seed + 1, start + 4 * 3600.0, (hours - 4) * 3600.0, faults)
    simulation = Simulation(topology, schedule, seed=seed)
    rows = []
    for index in range(int(hours * 60)):
        for reading in simulation.step(start + index * 60.0, 60.0):
            rows.append((reading.ts, reading.device_key, reading.metric, reading.value))
    frame = pd.DataFrame(rows, columns=["ts", "device_key", "metric", "value"])
    frame["ts"] = pd.to_datetime(frame["ts"], unit="s", utc=True)
    return frame, schedule, topology


def score_series(loaded, frame: pd.DataFrame) -> dict[tuple[str, str], list[tuple[float, bool, bool]]]:
    task, window = loaded.task, loaded.window
    results: dict[tuple[str, str], list[tuple[float, bool, bool]]] = defaultdict(list)
    for device_key, device_frame in device_frames(frame, task, window.step_s).items():
        values = to_model_space(device_frame.to_numpy(), task)
        times = epoch_seconds(device_frame.index)
        scaled = loaded.scaler.transform(values)
        length = window.input_len
        starts = np.arange(0, len(scaled) - length + 1)
        windows = np.stack([scaled[start : start + length] for start in starts]).astype(np.float32)
        with torch.no_grad():
            outputs = np.concatenate(
                [loaded.model(torch.from_numpy(windows[i : i + 2048])).numpy() for i in range(0, len(windows), 2048)]
            )
        outputs = loaded.scaler.inverse_targets(outputs, task.target_index)
        for position, target in enumerate(task.targets):
            threshold = threshold_for(device_type_of(device_key), target)
            if threshold is None:
                continue
            model_threshold = to_model_threshold(threshold)
            feature_index = task.features.index(target)
            std = loaded.residual_std[:, position]
            for offset in range(1, len(starts)):
                end = starts[offset] + length - 1
                history = values[end - 9 : end + 1, feature_index]
                z = residual_zscore(values[end, feature_index], outputs[offset - 1, 0, position], std[0])
                result = assess(history, outputs[offset, :, position], std, model_threshold, window.step_s, z)
                current = result.current_severity is not None
                forecast_only = (not current) and result.score >= ALERT_SCORE
                results[(device_key, target)].append((times[end], current or forecast_only, forecast_only))
    return results


def evaluate(series_scores, schedule: FaultSchedule, topology: Topology, frame: pd.DataFrame) -> dict:
    affected = [(spec, affected_series(spec, topology)) for spec in schedule.specs]
    tp = fp = fn = tn = 0
    for (device_key, metric), samples in series_scores.items():
        for t, alerted, _ in samples:
            positive = any((device_key, metric) in series and spec.intensity(t) >= ACTIVE_INTENSITY for spec, series in affected)
            if positive and alerted:
                tp += 1
            elif positive:
                fn += 1
            elif alerted:
                fp += 1
            else:
                tn += 1
    per_kind: dict[str, dict] = defaultdict(lambda: {"faults": 0, "detected": 0, "delays_min": []})
    lead_minutes = []
    for spec, series in affected:
        entry = per_kind[spec.kind.value]
        entry["faults"] += 1
        first_alert = None
        for key in series:
            for t, alerted, _ in series_scores.get(key, []):
                if alerted and spec.start_s <= t <= spec.end_s + spec.recovery_s:
                    first_alert = t if first_alert is None else min(first_alert, t)
                    break
        if first_alert is not None:
            entry["detected"] += 1
            entry["delays_min"].append(round((first_alert - spec.start_s) / 60.0, 1))
        for key in series:
            samples = series_scores.get(key, [])
            device_type = device_type_of(key[0])
            threshold = threshold_for(device_type, key[1])
            crossing = next((t for t, _, _ in samples if spec.start_s <= t <= spec.end_s and breached(frame, key, t, threshold)), None)
            forecast_alert = next((t for t, _, forecast_only in samples if forecast_only and spec.start_s <= t <= spec.end_s), None)
            if crossing is not None and forecast_alert is not None and forecast_alert <= crossing:
                lead_minutes.append((crossing - forecast_alert) / 60.0)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    kinds = {
        kind: {
            "faults": entry["faults"],
            "detected": entry["detected"],
            "median_detection_delay_min": statistics.median(entry["delays_min"]) if entry["delays_min"] else None,
        }
        for kind, entry in per_kind.items()
    }
    detected = sum(entry["detected"] for entry in per_kind.values())
    total = sum(entry["faults"] for entry in per_kind.values())
    return {
        "samples": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0,
        "fault_level": {"faults": total, "detected": detected, "recall": round(detected / total, 4) if total else None},
        "by_kind": kinds,
        "forecast_lead_minutes_median": round(statistics.median(lead_minutes), 1) if lead_minutes else None,
        "forecast_lead_samples": len(lead_minutes),
    }


_VALUE_CACHE: dict[int, dict] = {}


def breached(frame: pd.DataFrame, key: tuple[str, str], t: float, threshold) -> bool:
    cache = _VALUE_CACHE.setdefault(id(frame), {})
    if key not in cache:
        subset = frame[(frame["device_key"] == key[0]) & (frame["metric"] == key[1])]
        cache[key] = dict(zip(epoch_seconds(pd.DatetimeIndex(subset["ts"])), subset["value"]))
    value = cache[key].get(t)
    return value is not None and threshold is not None and threshold.breached(value) is not None


def main() -> None:
    parser = argparse.ArgumentParser(description="Risk detection precision and recall against injected faults")
    parser.add_argument("--checkpoints", type=Path, default=Path("checkpoints/bench"))
    parser.add_argument("--hours", type=float, default=48.0)
    parser.add_argument("--faults", type=int, default=8)
    parser.add_argument("--racks", type=int, default=6)
    parser.add_argument("--seed", type=int, default=101)
    parser.add_argument("--out", type=Path, default=Path("results/risk_detection.json"))
    args = parser.parse_args()
    torch.set_num_threads(1)
    start = 1_790_000_000.0
    frame, schedule, topology = simulate(args.hours, args.seed, args.faults, args.racks, start)
    combined: dict[tuple[str, str], list] = {}
    for name in TASKS:
        loaded = load_checkpoint(args.checkpoints / f"{name}.pt")
        combined.update(score_series(loaded, frame))
    report = {
        "setup": {"hours": args.hours, "faults": args.faults, "racks": args.racks, "seed": args.seed, "alert_score": ALERT_SCORE, "active_intensity": ACTIVE_INTENSITY},
        **evaluate(combined, schedule, topology, frame),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
