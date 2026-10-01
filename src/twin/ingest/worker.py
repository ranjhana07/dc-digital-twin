import logging
import signal
import threading
import time

import paho.mqtt.client as mqtt
import psycopg2

from twin.common.config import Settings, get_settings
from twin.common.topics import SUBSCRIPTION
from twin.common.topology import build_topology
from twin.db.topology_sync import upsert_topology
from twin.ingest.batcher import Batcher
from twin.ingest.sink import PostgresSink
from twin.ingest.validate import Validator

log = logging.getLogger("twin.ingest")

PARTITION_DAYS_AHEAD = 3


def maintain(dsn: str, refresh_rollups: bool = True) -> None:
    with psycopg2.connect(dsn) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ensure_telemetry_partitions(((now() AT TIME ZONE 'UTC')::date - 1), %s)",
                (PARTITION_DAYS_AHEAD + 1,),
            )
        if refresh_rollups:
            with conn.cursor() as cur:
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY telemetry_1m")
                cur.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY telemetry_1h")


class IngestWorker:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.validator = Validator()
        self.sink = PostgresSink(settings.psycopg_dsn, settings.ingest_mode)
        self.batcher: Batcher = Batcher(self.sink, settings.ingest_batch_size, settings.ingest_flush_seconds)
        self.stop = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="twin-ingest")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        if settings.mqtt_username:
            self.client.username_pw_set(settings.mqtt_username, settings.mqtt_password)

    def on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        log.info("connected to broker, subscribing to %s", SUBSCRIPTION)
        client.subscribe(SUBSCRIPTION, qos=self.settings.mqtt_qos)

    def on_message(self, client, userdata, message) -> None:
        reading = self.validator.check(message.topic, message.payload, time.time())
        if reading is not None:
            self.batcher.add(reading)

    def flush_loop(self) -> None:
        while not self.stop.wait(0.2):
            try:
                self.batcher.flush_if_due()
            except psycopg2.Error:
                time.sleep(1.0)

    def maintenance_loop(self, interval_s: float = 30.0) -> None:
        while not self.stop.is_set():
            try:
                maintain(self.settings.psycopg_dsn)
            except psycopg2.Error:
                log.exception("maintenance failed")
            self.stop.wait(interval_s)

    def report_loop(self, interval_s: float = 10.0) -> None:
        last_count, last_time = 0, time.monotonic()
        while not self.stop.wait(interval_s):
            now = time.monotonic()
            accepted = self.validator.stats.accepted
            rate = (accepted - last_count) / (now - last_time)
            last_count, last_time = accepted, now
            log.info(
                "accepted=%d rejected=%s rate=%.0f/s batches=%d",
                accepted,
                dict(self.validator.stats.rejected),
                rate,
                self.batcher.flushed_batches,
            )

    def run(self) -> None:
        topology = build_topology(
            self.settings.topo_sites,
            self.settings.topo_halls,
            self.settings.topo_racks_per_hall,
            self.settings.topo_servers_per_rack,
            self.settings.topo_cracs_per_hall,
            self.settings.topo_xcvrs_per_switch,
        )
        with psycopg2.connect(self.settings.psycopg_dsn) as conn:
            upsert_topology(conn, topology)
        maintain(self.settings.psycopg_dsn, refresh_rollups=False)
        for target in (self.flush_loop, self.maintenance_loop, self.report_loop):
            threading.Thread(target=target, daemon=True).start()
        signal.signal(signal.SIGTERM, lambda *_: self.stop.set())
        self.client.connect(self.settings.mqtt_host, self.settings.mqtt_port, keepalive=30)
        self.client.loop_start()
        try:
            self.stop.wait()
        except KeyboardInterrupt:
            self.stop.set()
        finally:
            self.client.loop_stop()
            self.client.disconnect()
            self.batcher.flush()
            self.sink.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    IngestWorker(get_settings()).run()


if __name__ == "__main__":
    main()
