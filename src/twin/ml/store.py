import json
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values

from twin.ml.inference import AlertSpec
from twin.ml.tasks import ForecastTask


def to_datetime(epoch_s: float) -> datetime:
    return datetime.fromtimestamp(epoch_s, tz=timezone.utc)


class PostgresForecastStore:
    def __init__(self, dsn: str, retain_minutes: int = 180) -> None:
        self.dsn = dsn
        self.retain_minutes = retain_minutes
        self._conn = None

    def connection(self):
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.dsn)
        return self._conn

    def metric_rows(self, task: ForecastTask, since_epoch: float) -> list[tuple[str, str, float, float]]:
        pattern = {"server": "%/srv-%", "pdu": "%/pdu-%", "transceiver": "%/xcvr-%"}[task.device_type.value]
        conn = self.connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT device_key, metric, extract(epoch FROM bucket), avg_value FROM telemetry_1m "
                "WHERE bucket >= %s AND metric = ANY(%s) AND device_key LIKE %s",
                (to_datetime(since_epoch), list(task.features), pattern),
            )
            rows = [(key, metric, float(bucket), float(value)) for key, metric, bucket, value in cur.fetchall()]
        conn.commit()
        return rows

    def write_predictions(self, rows: list[tuple]) -> None:
        converted = [
            (key, metric, task, to_datetime(made_at), to_datetime(target_ts), step, mean, lower, upper, version)
            for key, metric, task, made_at, target_ts, step, mean, lower, upper, version in rows
        ]
        conn = self.connection()
        with conn.cursor() as cur:
            execute_values(
                cur,
                "INSERT INTO predictions (device_key, metric, task, made_at, target_ts, horizon_step, "
                "predicted, lower, upper, model_version) VALUES %s",
                converted,
            )
            cur.execute(
                "DELETE FROM predictions WHERE made_at < now() - make_interval(mins => %s)", (self.retain_minutes,)
            )
        conn.commit()

    def upsert_risk(self, rows: list[tuple]) -> None:
        converted = [(*row[:3], to_datetime(row[3]), *row[4:]) for row in rows]
        conn = self.connection()
        with conn.cursor() as cur:
            execute_values(
                cur,
                "INSERT INTO risk_scores (device_key, metric, task, computed_at, risk, severity, p_warn, p_crit, "
                "rate_per_hour, z_score, breach_step) VALUES %s "
                "ON CONFLICT (device_key, metric) DO UPDATE SET task = EXCLUDED.task, computed_at = EXCLUDED.computed_at, "
                "risk = EXCLUDED.risk, severity = EXCLUDED.severity, p_warn = EXCLUDED.p_warn, p_crit = EXCLUDED.p_crit, "
                "rate_per_hour = EXCLUDED.rate_per_hour, z_score = EXCLUDED.z_score, breach_step = EXCLUDED.breach_step",
                converted,
            )
        conn.commit()

    def open_alert(self, spec: AlertSpec) -> None:
        conn = self.connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO alerts (device_key, rack_key, metric, kind, severity, message, risk_score, details) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (device_key, metric, kind) WHERE status <> 'resolved' "
                "DO UPDATE SET severity = EXCLUDED.severity, message = EXCLUDED.message, risk_score = EXCLUDED.risk_score",
                (
                    spec.device_key,
                    spec.rack_key,
                    spec.metric,
                    spec.kind,
                    spec.severity,
                    spec.message,
                    spec.risk_score,
                    json.dumps({}),
                ),
            )
        conn.commit()

    def resolve_alerts(self, device_key: str, metric: str, keep_kind: str | None) -> None:
        conn = self.connection()
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE alerts SET status = 'resolved', resolved_at = now() "
                "WHERE device_key = %s AND metric = %s AND status <> 'resolved' AND (%s::text IS NULL OR kind <> %s)",
                (device_key, metric, keep_kind, keep_kind),
            )
        conn.commit()
