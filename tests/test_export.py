import csv
import json

from twin.simulator.export import export_csv, write_fault_labels


def test_export_writes_long_format_and_labels(tmp_path):
    out = tmp_path / "telemetry.csv"
    schedule = export_csv(out, hours=6, step_s=300, start_epoch=1_780_000_000, seed=2, fault_count=2, racks=2, halls=1, servers=2)
    with out.open() as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0].keys() == {"ts", "device_key", "metric", "value"}
    assert len({row["ts"] for row in rows}) == 72
    labels = tmp_path / "telemetry.faults.json"
    write_fault_labels(labels, schedule)
    parsed = json.loads(labels.read_text())
    assert len(parsed) == 2
    assert {"kind", "target", "start_s", "end_s"} <= parsed[0].keys()
