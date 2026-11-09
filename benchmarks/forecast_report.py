import argparse
import csv
import json
from pathlib import Path

REPORT_HORIZONS = (5, 15, 30)


def load_metrics(checkpoint_dir: Path) -> dict[str, dict]:
    return {path.name.removesuffix(".metrics.json"): json.loads(path.read_text()) for path in sorted(checkpoint_dir.glob("*.metrics.json"))}


def summary_rows(metrics: dict[str, dict]) -> list[dict]:
    rows = []
    for task, report in metrics.items():
        for target, gru in report["gru_summary"].items():
            baseline = report["persistence_summary"][target]
            rows.append(
                {
                    "task": task,
                    "target": target,
                    "gru_mae": round(gru["mae"], 4),
                    "persistence_mae": round(baseline["mae"], 4),
                    "mae_reduction_pct": round(100 * (1 - gru["mae"] / baseline["mae"]), 1),
                    "gru_rmse": round(gru["rmse"], 4),
                    "persistence_rmse": round(baseline["rmse"], 4),
                    "rmse_reduction_pct": round(100 * (1 - gru["rmse"] / baseline["rmse"]), 1),
                    "gru_mape_pct": round(gru["mape"], 3),
                    "persistence_mape_pct": round(baseline["mape"], 3),
                    "test_windows": report["test_windows"],
                }
            )
    return rows


def horizon_rows(metrics: dict[str, dict]) -> list[dict]:
    rows = []
    for task, report in metrics.items():
        for target in report["gru"]:
            for minutes in REPORT_HORIZONS:
                index = minutes - 1
                rows.append(
                    {
                        "task": task,
                        "target": target,
                        "horizon_min": minutes,
                        "gru_mae": round(report["gru"][target]["mae"][index], 4),
                        "persistence_mae": round(report["persistence"][target]["mae"][index], 4),
                        "gru_rmse": round(report["gru"][target]["rmse"][index], 4),
                        "persistence_rmse": round(report["persistence"][target]["rmse"][index], 4),
                    }
                )
    return rows


def training_rows(metrics: dict[str, dict]) -> list[dict]:
    return [
        {
            "task": task,
            "epochs_run": report["epochs_run"],
            "train_seconds": round(sum(item["seconds"] for item in report["history"]), 1),
            "best_val_loss": round(min(item["val_loss"] for item in report["history"]), 5),
        }
        for task, report in metrics.items()
    ]


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect forecast accuracy from trained checkpoints")
    parser.add_argument("--checkpoints", type=Path, default=Path("checkpoints/bench"))
    parser.add_argument("--out", type=Path, default=Path("results"))
    args = parser.parse_args()
    metrics = load_metrics(args.checkpoints)
    write_csv(args.out / "forecast_summary.csv", summary_rows(metrics))
    write_csv(args.out / "forecast_per_horizon.csv", horizon_rows(metrics))
    write_csv(args.out / "training.csv", training_rows(metrics))
    for row in summary_rows(metrics):
        print(row)


if __name__ == "__main__":
    main()
