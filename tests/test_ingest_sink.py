import pytest

from twin.common.topics import Reading
from twin.ingest.sink import PostgresSink, copy_buffer, format_ts, insert_rows


def test_format_ts_is_utc_with_microseconds():
    assert format_ts(0.0) == "1970-01-01 00:00:00.000000+00"
    assert format_ts(1_780_000_000.25) == "2026-05-28 20:26:40.250000+00"


def test_copy_buffer_lines():
    readings = [Reading("dc1/hall-a/r01/srv-01", "inlet_temp", 0.0, 22.5), Reading("dc1/hall-a/r01/xcvr-1", "pre_fec_ber", 1.0, 1.2e-09)]
    lines = copy_buffer(readings).read().splitlines()
    assert lines[0] == "1970-01-01 00:00:00.000000+00,dc1/hall-a/r01/srv-01,inlet_temp,22.5"
    assert lines[1].endswith("dc1/hall-a/r01/xcvr-1,pre_fec_ber,1.2e-09")


def test_insert_rows_shape():
    rows = insert_rows([Reading("k", "power_w", 10.0, 300.0)])
    assert rows == [("1970-01-01 00:00:10.000000+00", "k", "power_w", 300.0)]


def test_unknown_mode_rejected():
    with pytest.raises(ValueError):
        PostgresSink("postgresql://x", mode="bulk")
