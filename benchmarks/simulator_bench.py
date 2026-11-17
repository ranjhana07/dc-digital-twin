import argparse
import json
import time
from pathlib import Path

from twin.common.payload import encode_payload
from twin.common.topology import build_topology
from twin.simulator.engine import Simulation
from twin.simulator.publisher import topic_for


def measure(halls: int, racks: int, steps: int, with_encoding: bool) -> dict:
    topology = build_topology(halls=halls, racks_per_hall=racks)
    simulation = Simulation(topology, seed=7)
    simulation.step(0.0)
    readings_total = 0
    started = time.perf_counter()
    for index in range(steps):
        readings = simulation.step(1_780_000_000.0 + index * 5.0, 5.0)
        readings_total += len(readings)
        if with_encoding:
            for reading in readings:
                topic_for(reading)
                encode_payload(reading.ts, reading.value, reading.metric)
    elapsed = time.perf_counter() - started
    return {
        "racks": halls * racks,
        "devices": len(topology.devices),
        "stage": "step+topic+payload" if with_encoding else "step",
        "steps": steps,
        "readings": readings_total,
        "seconds": round(elapsed, 3),
        "readings_per_s": round(readings_total / elapsed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure simulator message generation throughput without a broker")
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--out", type=Path, default=Path("results/simulator_throughput.json"))
    args = parser.parse_args()
    rows = []
    for halls, racks in ((2, 6), (4, 12)):
        for with_encoding in (False, True):
            rows.append(measure(halls, racks, args.steps, with_encoding))
            print(rows[-1])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, indent=2) + "\n")


if __name__ == "__main__":
    main()
