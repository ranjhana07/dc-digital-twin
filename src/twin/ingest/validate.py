from collections import Counter
from dataclasses import dataclass, field

from twin.common.metrics import ALL_METRICS
from twin.common.payload import PayloadError, decode_payload
from twin.common.topics import Reading, TopicError, parse_topic

MAX_SKEW_S = 86400.0


@dataclass
class IngestStats:
    accepted: int = 0
    rejected: Counter = field(default_factory=Counter)

    @property
    def rejected_total(self) -> int:
        return sum(self.rejected.values())


def parse_message(topic: str, payload: bytes, now_s: float, max_skew_s: float = MAX_SKEW_S) -> tuple[Reading | None, str | None]:
    try:
        parts = parse_topic(topic)
    except TopicError:
        return None, "topic"
    if parts.metric not in ALL_METRICS:
        return None, "metric"
    try:
        ts, value = decode_payload(payload)
    except PayloadError:
        return None, "payload"
    if abs(now_s - ts) > max_skew_s:
        return None, "skew"
    return Reading(parts.device_key, parts.metric, ts, value), None


class Validator:
    def __init__(self, max_skew_s: float = MAX_SKEW_S) -> None:
        self.max_skew_s = max_skew_s
        self.stats = IngestStats()

    def check(self, topic: str, payload: bytes, now_s: float) -> Reading | None:
        reading, reason = parse_message(topic, payload, now_s, self.max_skew_s)
        if reading is None:
            self.stats.rejected[reason] += 1
            return None
        self.stats.accepted += 1
        return reading
