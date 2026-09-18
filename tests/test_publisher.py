import pytest

from twin.common.topics import Reading, parse_topic
from twin.simulator.publisher import Pacer, topic_for


def test_topic_for_reading():
    reading = Reading("dc1/hall-a/r01/srv-01", "fan_rpm", 1.0, 4000.0)
    assert topic_for(reading) == "dc/dc1/hall-a/r01/srv-01/fan_rpm"
    assert parse_topic(topic_for(reading)).device_key == reading.device_key


def test_pacer_by_rate():
    pacer = Pacer(rate=1000.0, tick_s=5.0)
    assert pacer.delay_for(500, 0.1) == pytest.approx(0.4)
    assert pacer.delay_for(500, 1.0) == 0.0


def test_pacer_by_tick_and_speed():
    pacer = Pacer(rate=0.0, tick_s=5.0, speed=10.0)
    assert pacer.delay_for(100, 0.1) == pytest.approx(0.4)
