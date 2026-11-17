import argparse
import csv
import json
from pathlib import Path


def table(headers: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def read_csv(path: Path) -> list[dict]:
    with path.open() as handle:
        return list(csv.DictReader(handle))


def hardware_section(results: Path) -> str:
    info = json.loads((results / "hardware.json").read_text())
    return (
        f"Measured on {info['cpu']} ({info['logical_cores']} logical cores), {info['os']}, "
        f"Python {info['python']}, torch {info['torch']} (CPU)."
    )


def simulator_section(results: Path) -> str:
    rows = json.loads((results / "simulator_throughput.json").read_text())
    return table(
        ["racks", "devices", "stage", "readings", "seconds", "readings/s"],
        [[r["racks"], r["devices"], r["stage"], r["readings"], r["seconds"], f"{r['readings_per_s']:,}"] for r in rows],
    )


def forecast_section(results: Path) -> str:
    summary = read_csv(results / "forecast_summary.csv")
    main = table(
        ["task", "target", "GRU MAE", "persistence MAE", "MAE change", "GRU RMSE", "persistence RMSE", "RMSE change", "test windows"],
        [
            [
                r["task"], r["target"], r["gru_mae"], r["persistence_mae"], f"-{r['mae_reduction_pct']}%",
                r["gru_rmse"], r["persistence_rmse"], f"-{r['rmse_reduction_pct']}%", r["test_windows"],
            ]
            for r in summary
        ],
    )
    horizon = table(
        ["task", "target", "horizon", "GRU MAE", "persistence MAE", "GRU RMSE", "persistence RMSE"],
        [
            [r["task"], r["target"], f"{r['horizon_min']} min", r["gru_mae"], r["persistence_mae"], r["gru_rmse"], r["persistence_rmse"]]
            for r in read_csv(results / "forecast_per_horizon.csv")
        ],
    )
    training = table(
        ["task", "epochs run", "train seconds", "best val loss"],
        [[r["task"], r["epochs_run"], r["train_seconds"], r["best_val_loss"]] for r in read_csv(results / "training.csv")],
    )
    return f"{main}\n\nBy horizon:\n\n{horizon}\n\nTraining:\n\n{training}"


def latency_section(results: Path) -> str:
    report = json.loads((results / "inference_latency.json").read_text())
    forward = table(
        ["task", "engine", "batch", "p50 ms", "p95 ms", "ms per series"],
        [[r["task"], r["engine"], r["batch"], r["p50_ms"], r["p95_ms"], r["per_series_ms"]] for r in report["forward_pass"]],
    )
    cycle = table(
        ["devices", "p50 ms", "p95 ms", "ms per device"],
        [[r["devices"], r["p50_ms"], r["p95_ms"], r["per_device_ms"]] for r in report["service_cycle_thermal"]],
    )
    return f"Torch threads: {report['torch_threads']}.\n\n{forward}\n\nFull thermal cycle (assemble windows, two forecasts per device, risk and alert specs, in-memory store):\n\n{cycle}"


def risk_section(results: Path) -> str:
    report = json.loads((results / "risk_detection.json").read_text())
    setup, samples, fault_level = report["setup"], report["samples"], report["fault_level"]
    kinds = table(
        ["fault kind", "faults", "detected", "median delay after onset (min)"],
        [[kind, v["faults"], v["detected"], v["median_detection_delay_min"]] for kind, v in report["by_kind"].items()],
    )
    return (
        f"{setup['hours']:.0f} simulated hours, {setup['faults']} injected faults, {setup['racks']} racks, seed {setup['seed']}, "
        f"alert at risk >= {setup['alert_score']} or a current threshold breach.\n\n"
        f"- Sample level: precision {report['precision']}, recall {report['recall']}, F1 {report['f1']} "
        f"(TP {samples['tp']}, FP {samples['fp']}, FN {samples['fn']}, TN {samples['tn']}).\n"
        f"- Fault level: {fault_level['detected']} of {fault_level['faults']} faults raised an alert on an affected series during the fault.\n"
        f"- Median lead of a forecast-only alert over the first threshold breach: {report['forecast_lead_minutes_median']} min "
        f"({report['forecast_lead_samples']} series).\n\n{kinds}"
    )


def rca_section(results: Path) -> str:
    report = json.loads((results / "rca_accuracy.json").read_text())
    single, dual = report["single_fault"], report["dual_fault"]
    kinds = table(
        ["fault kind", "incidents", "top-1", "top-3"],
        [[kind, v["incidents"], v["top1"], v["top3"]] for kind, v in single["by_kind"].items()],
    )
    return (
        f"Single fault, {single['incidents']} incidents: top-1 {single['top1_accuracy']}, top-3 {single['top3_accuracy']}.\n\n{kinds}\n\n"
        f"Two concurrent faults, {dual['incidents']} incidents: top-1 is a true cause in {dual['top1_is_a_true_cause']} of them, "
        f"both true causes within the top 3 in {dual['both_causes_in_top3']}."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render results/ into markdown")
    parser.add_argument("--results", type=Path, default=Path("results"))
    args = parser.parse_args()
    sections = [
        ("Hardware", hardware_section),
        ("Simulator throughput", simulator_section),
        ("Forecast accuracy", forecast_section),
        ("Inference latency", latency_section),
        ("Risk detection", risk_section),
        ("Root cause ranking", rca_section),
    ]
    for title, render in sections:
        if title == "Hardware":
            print(render(args.results))
            print()
            continue
        print(f"### {title}\n")
        print(render(args.results))
        print()


if __name__ == "__main__":
    main()
