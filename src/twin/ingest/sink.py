import io
import logging
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from twin.common.topics import Reading

log = logging.getLogger("twin.ingest")

COPY_SQL = "COPY telemetry (ts, device_key, metric, value) FROM STDIN WITH (FORMAT csv)"
INSERT_SQL = "INSERT INTO telemetry (ts, device_key, metric, value) VALUES %s"


def format_ts(epoch_s: float) -> str:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f+00")


def copy_buffer(readings: list[Reading]) -> io.StringIO:
    buffer = io.StringIO()
    for reading in readings:
        buffer.write(f"{format_ts(reading.ts)},{reading.device_key},{reading.metric},{reading.value!r}\n")
    buffer.seek(0)
    return buffer


def insert_rows(readings: list[Reading]) -> list[tuple[str, str, str, float]]:
    return [(format_ts(r.ts), r.device_key, r.metric, r.value) for r in readings]


class PostgresSink:
    def __init__(self, dsn: str, mode: str = "copy") -> None:
        if mode not in ("copy", "values"):
            raise ValueError(f"unknown ingest mode: {mode}")
        self.dsn = dsn
        self.mode = mode
        self._conn = None

    def connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
            self._conn.autocommit = False
        return self._conn

    def __call__(self, readings: list[Reading]) -> None:
        try:
            conn = self.connection()
            with conn.cursor() as cur:
                if self.mode == "copy":
                    cur.copy_expert(COPY_SQL, copy_buffer(readings))
                else:
                    execute_values(cur, INSERT_SQL, insert_rows(readings), page_size=len(readings))
            conn.commit()
        except psycopg2.Error:
            log.exception("failed to write %d readings", len(readings))
            if self._conn is not None and not self._conn.closed:
                self._conn.rollback()
            self._conn = None
            raise

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
