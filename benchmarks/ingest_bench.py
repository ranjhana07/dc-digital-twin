import argparse
import json
import time

import psycopg2

from twin.common.config import get_settings
from twin.common.topology import build_topology
from twin.ingest.sink import PostgresSink
from twin.simulator.engine import Simulation


def generate(count: int, racks: int) -> list:
    topology = build_topology(halls=2, racks_per_hall=racks)
    simulation = Simulation(topology)
    readings: list = []
    t = time.time()
    while len(readings) < count:
        readings.extend(simulation.step(t))
        t += 5.0
    return readings[:count]


def run(dsn: str, mode: str, readings: list, batch_size: int) -> dict:
    sink = PostgresSink(dsn, mode)
    started = time.perf_counter()
    for offset in range(0, len(readings), batch_size):
        sink(readings[offset : offset + batch_size])
    elapsed = time.perf_counter() - started
    sink.close()
    return {"mode": mode, "batch_size": batch_size, "rows": len(readings), "seconds": round(elapsed, 3), "rows_per_s": round(len(readings) / elapsed)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure batch insert throughput into the telemetry table")
    parser.add_argument("--dsn", default=get_settings().psycopg_dsn)
    parser.add_argument("--rows", type=int, default=200_000)
    parser.add_argument("--batch-sizes", type=int, nargs="+", default=[500, 2000, 10000])
    parser.add_argument("--out", default="results/ingest_bench.json")
    args = parser.parse_args()
    with psycopg2.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT ensure_telemetry_partitions(((now() AT TIME ZONE 'UTC')::date - 1), 4)")
    readings = generate(args.rows, racks=6)
    results = [run(args.dsn, mode, readings, size) for mode in ("values", "copy") for size in args.batch_sizes]
    with open(args.out, "w") as handle:
        json.dump(results, handle, indent=2)
    for row in results:
        print(row)


if __name__ == "__main__":
    main()
