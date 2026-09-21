CREATE MATERIALIZED VIEW telemetry_1m AS
SELECT
    date_trunc('minute', ts) AS bucket,
    device_key,
    metric,
    avg(value) AS avg_value,
    min(value) AS min_value,
    max(value) AS max_value,
    count(*) AS samples
FROM telemetry
GROUP BY 1, 2, 3
WITH NO DATA;

CREATE UNIQUE INDEX telemetry_1m_key_idx ON telemetry_1m (device_key, metric, bucket);
CREATE INDEX telemetry_1m_bucket_idx ON telemetry_1m (bucket DESC);

CREATE MATERIALIZED VIEW telemetry_1h AS
SELECT
    date_trunc('hour', bucket) AS bucket,
    device_key,
    metric,
    sum(avg_value * samples) / sum(samples) AS avg_value,
    min(min_value) AS min_value,
    max(max_value) AS max_value,
    sum(samples) AS samples
FROM telemetry_1m
GROUP BY 1, 2, 3
WITH NO DATA;

CREATE UNIQUE INDEX telemetry_1h_key_idx ON telemetry_1h (device_key, metric, bucket);

CREATE VIEW latest_telemetry AS
SELECT DISTINCT ON (device_key, metric) device_key, metric, value, ts
FROM telemetry
WHERE ts > now() - interval '15 minutes'
ORDER BY device_key, metric, ts DESC;
