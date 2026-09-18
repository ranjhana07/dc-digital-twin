import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

from twin.common.topology import build_topology
from twin.simulator.engine import Simulation
from twin.simulator.faults import FaultSchedule, random_schedule

DEFAULT_START = "2026-01-05T00:00:00+00:00"


def export_csv(
    out_path: Path,
    hours: float,
    step_s: float,
    start_epoch: float,
    seed: int,
    fault_count: int,
    racks: int,
    halls: int,
    servers: int,
) -> FaultSchedule:
    topology = build_topology(halls=halls, racks_per_hall=racks, servers_per_rack=servers)
    horizon_s = hours * 3600.0
    schedule = FaultSchedule()
    if fault_count:
        schedule = random_schedule(
            topology, seed=seed + 1, start_s=start_epoch + 4 * 3600.0, horizon_s=horizon_s - 4 * 3600.0, count=fault_count
        )
    simulation = Simulation(topology, schedule, seed=seed)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ts", "device_key", "metric", "value"])
        steps = int(horizon_s // step_s)
        for index in range(steps):
            t = start_epoch + index * step_s
            for reading in simulation.step(t, step_s):
                writer.writerow([f"{reading.ts:.0f}", reading.device_key, reading.metric, reading.value])
    return schedule


def write_fault_labels(path: Path, schedule: FaultSchedule) -> None:
    rows = [
        {
            "kind": spec.kind.value,
            "target": spec.target,
            "start_s": spec.start_s,
            "end_s": spec.end_s,
            "ramp_s": spec.ramp_s,
            "magnitude": round(spec.magnitude, 3),
        }
        for spec in schedule.specs
    ]
    path.write_text(json.dumps(rows, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="twin.simulator.export", description="Write simulated telemetry to CSV")
    parser.add_argument("--out", type=Path, default=Path("data/telemetry.csv"))
    parser.add_argument("--hours", type=float, default=72.0)
    parser.add_argument("--step", type=float, default=60.0, help="simulated seconds between samples")
    parser.add_argument("--start", default=DEFAULT_START)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--faults", type=int, default=12)
    parser.add_argument("--halls", type=int, default=2)
    parser.add_argument("--racks", type=int, default=6)
    parser.add_argument("--servers", type=int, default=4)
    args = parser.parse_args()
    start_epoch = datetime.fromisoformat(args.start).astimezone(timezone.utc).timestamp()
    schedule = export_csv(
        args.out, args.hours, args.step, start_epoch, args.seed, args.faults, args.racks, args.halls, args.servers
    )
    labels_path = args.out.with_suffix(".faults.json")
    write_fault_labels(labels_path, schedule)
    print(f"wrote {args.out} and {labels_path} ({len(schedule.specs)} faults)")


if __name__ == "__main__":
    main()
