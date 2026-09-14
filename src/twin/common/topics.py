import re
from dataclasses import dataclass

TOPIC_ROOT = "dc"
SUBSCRIPTION = f"{TOPIC_ROOT}/+/+/+/+/+"
SEGMENT_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class TopicError(ValueError):
    pass


@dataclass(frozen=True)
class TopicParts:
    site: str
    hall: str
    rack: str
    device: str
    metric: str

    @property
    def device_key(self) -> str:
        return f"{self.site}/{self.hall}/{self.rack}/{self.device}"


def build_topic(site: str, hall: str, rack: str, device: str, metric: str) -> str:
    segments = (site, hall, rack, device, metric)
    for segment in segments:
        if not SEGMENT_PATTERN.match(segment):
            raise TopicError(f"invalid topic segment: {segment!r}")
    return "/".join((TOPIC_ROOT, *segments))


def parse_topic(topic: str) -> TopicParts:
    segments = topic.split("/")
    if len(segments) != 6 or segments[0] != TOPIC_ROOT:
        raise TopicError(f"unexpected topic shape: {topic!r}")
    for segment in segments[1:]:
        if not SEGMENT_PATTERN.match(segment):
            raise TopicError(f"invalid topic segment: {segment!r}")
    return TopicParts(*segments[1:])


@dataclass(frozen=True)
class Reading:
    device_key: str
    metric: str
    ts: float
    value: float
