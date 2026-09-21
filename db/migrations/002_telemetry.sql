CREATE TABLE telemetry (
    ts timestamptz NOT NULL,
    device_key text NOT NULL,
    metric text NOT NULL,
    value double precision NOT NULL
) PARTITION BY RANGE (ts);

CREATE TABLE telemetry_default PARTITION OF telemetry DEFAULT;

CREATE INDEX telemetry_series_idx ON telemetry (device_key, metric, ts DESC);

CREATE FUNCTION create_telemetry_partition(day date) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
    partition_name text := 'telemetry_' || to_char(day, 'YYYYMMDD');
BEGIN
    EXECUTE format(
        'CREATE TABLE IF NOT EXISTS %I PARTITION OF telemetry FOR VALUES FROM (%L) TO (%L)',
        partition_name,
        (day::timestamp AT TIME ZONE 'UTC'),
        ((day + 1)::timestamp AT TIME ZONE 'UTC')
    );
END
$$;

CREATE FUNCTION ensure_telemetry_partitions(first_day date, day_count integer) RETURNS integer
LANGUAGE plpgsql AS $$
BEGIN
    FOR offset_days IN 0..day_count - 1 LOOP
        PERFORM create_telemetry_partition(first_day + offset_days);
    END LOOP;
    RETURN day_count;
END
$$;

SELECT ensure_telemetry_partitions((now() AT TIME ZONE 'UTC')::date - 1, 5);
