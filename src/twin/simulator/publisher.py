import logging
import time
from collections.abc import Iterable

import paho.mqtt.client as mqtt

from twin.common.payload import encode_payload
from twin.common.topics import Reading, build_topic

log = logging.getLogger("twin.simulator")


def topic_for(reading: Reading) -> str:
    site, hall, rack, device = reading.device_key.split("/")
    return build_topic(site, hall, rack, device, reading.metric)


class MqttPublisher:
    def __init__(self, host: str, port: int, username: str | None = None, password: str | None = None, qos: int = 0):
        self.qos = qos
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twin-simulator")
        if username:
            self.client.username_pw_set(username, password)
        self.host = host
        self.port = port
        self.published = 0

    def connect(self) -> None:
        self.client.connect(self.host, self.port, keepalive=30)
        self.client.loop_start()

    def close(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, readings: Iterable[Reading]) -> int:
        count = 0
        for reading in readings:
            self.client.publish(topic_for(reading), encode_payload(reading.ts, reading.value, reading.metric), qos=self.qos)
            count += 1
        self.published += count
        return count


class Pacer:
    def __init__(self, rate: float, tick_s: float, speed: float = 1.0) -> None:
        self.rate = rate
        self.tick_s = tick_s
        self.speed = speed

    def delay_for(self, message_count: int, elapsed_s: float) -> float:
        if self.rate > 0:
            budget = message_count / self.rate
        else:
            budget = self.tick_s / self.speed
        return max(budget - elapsed_s, 0.0)

    def wait(self, message_count: int, started: float) -> None:
        delay = self.delay_for(message_count, time.monotonic() - started)
        if delay > 0:
            time.sleep(delay)
