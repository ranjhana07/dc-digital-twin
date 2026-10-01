# ingest

Two interchangeable paths from MQTT into the `telemetry` table. Run one of them, not both.

- `mosquitto/mosquitto.conf` is the broker config.
- `node-red/` holds the Node-RED flow. It subscribes to `dc/+/+/+/+/+`, validates the topic and payload, joins messages into batches of 500 or one second, and inserts each batch with a single `unnest` statement. Connection details come from `MQTT_HOST` and the `PG*` variables.
- `src/twin/ingest` is the Python worker. It does the same validation, buffers readings in a `Batcher` and writes them with `COPY` (default) or `execute_values`. It also keeps daily partitions created ahead of time and refreshes the rollup views.

Rejected messages are counted by reason: `topic`, `metric`, `payload`, `skew`.
