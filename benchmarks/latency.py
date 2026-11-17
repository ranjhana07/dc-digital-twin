import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch

from twin.ml.checkpoint import load_checkpoint
from twin.ml.export import export_torchscript
from twin.ml.inference import TaskBundle
from twin.ml.tasks import TASKS


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(int(len(ordered) * fraction), len(ordered) - 1)]


def time_calls(call, repeats: int) -> list[float]:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        call()
        samples.append((time.perf_counter() - started) * 1000.0)
    return samples


def summarize(samples: list[float]) -> dict:
    return {
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": round(percentile(samples, 0.95), 3),
        "mean_ms": round(statistics.fmean(samples), 3),
    }


def measure_task(checkpoint: Path, repeats: int, fleet_sizes: tuple[int, ...]) -> list[dict]:
    loaded = load_checkpoint(checkpoint)
    window = loaded.window
    shape = (window.input_len, len(loaded.task.features))
    scripted_path = checkpoint.with_suffix(".bench.ts")
    export_torchscript(loaded, scripted_path)
    scripted = torch.jit.load(str(scripted_path))
    rng = np.random.default_rng(0)
    rows = []
    for engine, model in (("eager", loaded.model), ("torchscript", scripted)):
        for batch_size in fleet_sizes:
            batch = torch.from_numpy(rng.normal(size=(batch_size, *shape)).astype(np.float32))

            def call(batch=batch, model=model):
                with torch.no_grad():
                    model(batch)

            time_calls(call, 10)
            summary = summarize(time_calls(call, repeats))
            rows.append({"task": loaded.task.name, "engine": engine, "batch": batch_size, **summary, "per_series_ms": round(summary["p50_ms"] / batch_size, 4)})
    scripted_path.unlink()
    return rows


def measure_service_cycle(checkpoint_dir: Path, devices: int, repeats: int) -> dict:
    from twin.ml.inference import InferenceService, assemble_windows

    loaded = load_checkpoint(checkpoint_dir / "thermal.pt")
    task, window = loaded.task, loaded.window

    def forecast(batch: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            return loaded.model(torch.from_numpy(batch).float()).numpy()

    bundle = TaskBundle(task, window, loaded.scaler, loaded.residual_std, loaded.version, forecast)
    rng = np.random.default_rng(1)
    rows = []
    base = np.array([24.0, 34.0, 0.5, 5000.0, 300.0])
    for index in range(devices):
        key = f"dc1/hall-a/r{index // 8 + 1:02d}/srv-{index % 8 + 1:02d}"
        for step in range(window.input_len + 1):
            for position, name in enumerate(task.features):
                rows.append((key, name, 1_780_000_000.0 + step * 60, float(base[position] + rng.normal(scale=0.2))))

    class ReplayStore:
        def metric_rows(self, task, since_epoch):
            return rows

        def write_predictions(self, prediction_rows):
            pass

        def upsert_risk(self, risk_rows):
            pass

        def open_alert(self, spec):
            pass

        def resolve_alerts(self, device_key, metric, keep_kind):
            pass

    service = InferenceService({"thermal": bundle}, ReplayStore())
    samples = time_calls(lambda: service.run_once(1_780_000_000.0 + window.input_len * 60), repeats)
    assert len(assemble_windows(rows, task, window.input_len + 1)) == devices
    return {"devices": devices, **summarize(samples), "per_device_ms": round(statistics.median(samples) / devices, 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure forecast latency of trained checkpoints on CPU")
    parser.add_argument("--checkpoints", type=Path, default=Path("checkpoints/bench"))
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--out", type=Path, default=Path("results/inference_latency.json"))
    args = parser.parse_args()
    torch.set_num_threads(1)
    model_rows = []
    for name in TASKS:
        model_rows.extend(measure_task(args.checkpoints / f"{name}.pt", args.repeats, (1, 16, 64, 256)))
    cycle = [measure_service_cycle(args.checkpoints, devices, 10) for devices in (16, 64, 256)]
    report = {"torch_threads": torch.get_num_threads(), "forward_pass": model_rows, "service_cycle_thermal": cycle}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
