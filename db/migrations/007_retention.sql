CREATE FUNCTION drop_old_telemetry_partitions(retain_days integer) RETURNS integer
LANGUAGE plpgsql AS $$
DECLARE
    partition record;
    dropped integer := 0;
    cutoff text := 'telemetry_' || to_char((now() AT TIME ZONE 'UTC')::date - retain_days, 'YYYYMMDD');
BEGIN
    FOR partition IN
        SELECT c.relname
        FROM pg_inherits i
        JOIN pg_class c ON c.oid = i.inhrelid
        JOIN pg_class p ON p.oid = i.inhparent
        WHERE p.relname = 'telemetry' AND c.relname ~ '^telemetry_[0-9]{8}$' AND c.relname < cutoff
    LOOP
        EXECUTE format('DROP TABLE %I', partition.relname);
        dropped := dropped + 1;
    END LOOP;
    RETURN dropped;
END
$$;
