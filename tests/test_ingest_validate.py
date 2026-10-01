import pytest

from twin.common.payload import encode_payload
from twin.ingest.validate import Validator, parse_message

NOW = 1_780_000_000.0
TOPIC = "dc/dc1/hall-a/r01/srv-01/inlet_temp"


def test_accepts_valid_message():
    reading, reason = parse_message(TOPIC, encode_payload(NOW, 23.4), NOW)
    assert reason is None
    assert reading.device_key == "dc1/hall-a/r01/srv-01"
    assert reading.metric == "inlet_temp"
    assert reading.value == 23.4


@pytest.mark.parametrize(
    "topic, payload, expected",
    [
        ("dc/dc1/hall-a/srv-01/inlet_temp", encode_payload(NOW, 1.0), "topic"),
        ("dc/dc1/hall-a/r01/srv-01/humidity", encode_payload(NOW, 1.0), "metric"),
        (TOPIC, b"oops", "payload"),
        (TOPIC, encode_payload(NOW - 200000, 1.0), "skew"),
    ],
)
def test_rejection_reasons(topic, payload, expected):
    reading, reason = parse_message(topic, payload, NOW)
    assert reading is None
    assert reason == expected


def test_validator_counts():
    validator = Validator()
    assert validator.check(TOPIC, encode_payload(NOW, 20.0), NOW) is not None
    assert validator.check(TOPIC, b"x", NOW) is None
    assert validator.check("bad", b"x", NOW) is None
    assert validator.stats.accepted == 1
    assert validator.stats.rejected["payload"] == 1
    assert validator.stats.rejected_total == 2
