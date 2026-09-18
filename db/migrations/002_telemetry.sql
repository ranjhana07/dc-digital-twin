CREATE TABLE telemetry (
    ts timestamptz NOT NULL,
    device_key text NOT NULL,
    metric text NOT NULL,
    value double precision NOT NULL
) PARTITION BY RANGE (ts);

CREATE TABLE telemetry_default PARTITION OF telemetry DEFAULT;

CREATE INDEX telemetry_series_idx ON telemetry (device_key, metric, ts DESC);
