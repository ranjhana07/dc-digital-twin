import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from twin.common.metrics import THRESHOLDS
from twin.common.topology import Topology, build_topology, device_type_of
from twin.rca.engine import AlertRecord, rank_root_causes
from twin.rca.graph import AssetGraph
from twin.simulator.engine import Simulation
from twin.simulator.faults import FAULT_TARGET_TYPES, FaultKind, FaultSchedule, FaultSpec

SEVERITY_RANK = {"warning": 1, "critical": 2}
START = 1_790_000_000.0
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def threshold_alerts(readings_by_step: list[list], start_after: float) -> list[AlertRecord]:
    first_seen: dict[tuple[str, str], tuple[float, str]] = {}
    for readings in readings_by_step:
        for reading in readings:
            device_type = device_type_of(reading.device_key)
            threshold = THRESHOLDS.get((device_type, reading.metric))
            if threshold is None or reading.ts < start_after:
                continue
            severity = threshold.breached(reading.value)
            if severity is None:
                continue
            key = (reading.device_key, reading.metric)
            known = first_seen.get(key)
            if known is None:
                first_seen[key] = (reading.ts, severity)
            elif SEVERITY_RANK[severity] > SEVERITY_RANK[known[1]]:
                first_seen[key] = (known[0], severity)
    return [
        AlertRecord(index, key[0], key[1], severity, EPOCH + timedelta(seconds=ts))
        for index, (key, (ts, severity)) in enumerate(sorted(first_seen.items(), key=lambda item: item[1][0]), start=1)
    ]


def random_fault(topology: Topology, rng: random.Random, kind: FaultKind, start_s: float, duration_s: float) -> FaultSpec:
    candidates = sorted(device.key for device in topology.devices_of_type(FAULT_TARGET_TYPES[kind]))
    return FaultSpec(kind, rng.choice(candidates), start_s, duration_s, magnitude=rng.uniform(0.8, 1.0))


def run_incident(topology: Topology, graph: AssetGraph, specs: list[FaultSpec], seed: int, hours: float) -> tuple[list, list]:
    simulation = Simulation(topology, FaultSchedule(specs), seed=seed)
    steps = []
    for index in range(int(hours * 60)):
        steps.append(simulation.step(START + index * 60.0, 60.0))
    alerts = threshold_alerts(steps, START + 600.0)
    return rank_root_causes(alerts, graph, top_n=5), alerts


def evaluate_single(count: int, seed: int, racks: int, hours: float) -> dict:
    topology = build_topology(halls=1, racks_per_hall=racks)
    graph = AssetGraph(topology.edges)
    rng = random.Random(seed)
    outcomes: dict[str, dict] = {kind.value: {"incidents": 0, "top1": 0, "top3": 0, "no_alerts": 0} for kind in FaultKind}
    for index in range(count):
        kind = list(FaultKind)[index % len(FaultKind)]
        spec = random_fault(topology, rng, kind, START + 900.0, hours * 3600.0)
        ranking, alerts = run_incident(topology, graph, [spec], seed * 1000 + index, hours)
        entry = outcomes[kind.value]
        entry["incidents"] += 1
        if not ranking:
            entry["no_alerts"] += 1
            continue
        nodes = [candidate.node for candidate in ranking]
        entry["top1"] += int(nodes[0] == spec.target)
        entry["top3"] += int(spec.target in nodes[:3])
    total = sum(entry["incidents"] for entry in outcomes.values())
    top1 = sum(entry["top1"] for entry in outcomes.values())
    top3 = sum(entry["top3"] for entry in outcomes.values())
    return {"incidents": total, "top1_accuracy": round(top1 / total, 4), "top3_accuracy": round(top3 / total, 4), "by_kind": outcomes}


def evaluate_dual(count: int, seed: int, racks: int, hours: float) -> dict:
    topology = build_topology(halls=1, racks_per_hall=racks)
    graph = AssetGraph(topology.edges)
    rng = random.Random(seed)
    top1_is_a_cause = both_in_top3 = 0
    for index in range(count):
        first, second = rng.sample(list(FaultKind), 2)
        specs = [random_fault(topology, rng, first, START + 900.0, hours * 3600.0), random_fault(topology, rng, second, START + 1200.0, hours * 3600.0)]
        targets = {spec.target for spec in specs}
        ranking, _ = run_incident(topology, graph, specs, seed * 1000 + index, hours)
        nodes = [candidate.node for candidate in ranking]
        top1_is_a_cause += int(bool(nodes) and nodes[0] in targets)
        both_in_top3 += int(targets <= set(nodes[:3]))
    return {"incidents": count, "top1_is_a_true_cause": round(top1_is_a_cause / count, 4), "both_causes_in_top3": round(both_in_top3 / count, 4)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Root cause ranking accuracy on simulated incidents")
    parser.add_argument("--single", type=int, default=200)
    parser.add_argument("--dual", type=int, default=100)
    parser.add_argument("--racks", type=int, default=6)
    parser.add_argument("--hours", type=float, default=3.0)
    parser.add_argument("--seed", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("results/rca_accuracy.json"))
    args = parser.parse_args()
    report = {
        "setup": {"racks": args.racks, "window_hours": args.hours, "alert_source": "first threshold breach per device and metric"},
        "single_fault": evaluate_single(args.single, args.seed, args.racks, args.hours),
        "dual_fault": evaluate_dual(args.dual, args.seed + 1, args.racks, args.hours),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
