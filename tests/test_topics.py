import pytest

from twin.common.topics import TopicError, build_topic, parse_topic


def test_build_and_parse_roundtrip():
    topic = build_topic("dc1", "hall-a", "r01", "srv-01", "inlet_temp")
    assert topic == "dc/dc1/hall-a/r01/srv-01/inlet_temp"
    parts = parse_topic(topic)
    assert parts.site == "dc1"
    assert parts.metric == "inlet_temp"
    assert parts.device_key == "dc1/hall-a/r01/srv-01"


@pytest.mark.parametrize(
    "topic",
    [
        "dc/dc1/hall-a/r01/srv-01",
        "dc/dc1/hall-a/r01/srv-01/inlet_temp/extra",
        "xx/dc1/hall-a/r01/srv-01/inlet_temp",
        "dc/dc1/hall-a//srv-01/inlet_temp",
        "dc/dc1/hall a/r01/srv-01/inlet_temp",
    ],
)
def test_parse_rejects_bad_topics(topic):
    with pytest.raises(TopicError):
        parse_topic(topic)


def test_build_rejects_wildcards():
    with pytest.raises(TopicError):
        build_topic("dc1", "+", "r01", "srv-01", "inlet_temp")
