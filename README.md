# dc-digital-twin

A digital twin for data center infrastructure. A simulator stands in for the facility and publishes telemetry over MQTT. The data lands in PostgreSQL, GRU models forecast thermal, power and optical bit error rate behaviour, a topology-aware engine ranks probable root causes when alerts pile up, and a FastAPI service and a browser dashboard expose all of it.

Everything runs locally with Docker Compose. The tests need no database, broker or network.

## Architecture

```
  simulator --MQTT--> mosquitto --+--> ingest worker (Python, COPY) --+
  (sites, halls, racks,           |                                   |
   devices, faults)               +--> Node-RED flow (unnest insert) -+
                                                                      v
                                                       PostgreSQL (partitioned telemetry,
                                                       rollup views, assets, alerts, rca)
                                                          ^                    ^
                                                          |                    |
                                          inference service (GRU,        FastAPI (REST + WebSocket)
                                          risk scores, alerts)                 |
                                                                          nginx dashboard
                                                                          (ApexCharts, SVG topology)
```

The ingest worker and the Node-RED flow do the same job. Run one of them.

## Data model

Migrations live in `db/migrations` as plain SQL and run in file order.

| table or view | purpose |
| --- | --- |
| `sites`, `halls`, `racks`, `devices` | asset hierarchy, `devices.device_key` is `site/hall/rack/device` |
| `asset_edges` | dependency edges: `in_rack`, `cooled_by`, `powered_by`, `uplinks_to`, `part_of` |
| `telemetry` | `(ts, device_key, metric, value)`, range partitioned by day, with a default partition |
| `telemetry_1m`, `telemetry_1h` | materialized rollups, refreshed concurrently by the ingest worker |
| `latest_telemetry` | last value per device and metric over the past 15 minutes |
| `predictions` | forecast points with lower and upper bounds per horizon step |
| `risk_scores` | latest risk per device and metric |
| `alerts` | threshold and forecast alerts, one open alert per device, metric and kind |
| `rca_results` | ranked root cause candidates per analysis run |

`create_telemetry_partition(day)` and `ensure_telemetry_partitions(first_day, count)` create daily partitions. `drop_old_telemetry_partitions(retain_days)` removes old ones.

Devices and their metrics:

| type | metrics |
| --- | --- |
| server | cpu_load, power_w, fan_rpm, inlet_temp, outlet_temp |
| switch | power_w, fan_rpm, inlet_temp |
| transceiver | rx_power_dbm, tx_power_dbm, module_temp, pre_fec_ber |
| pdu | power_w, current_a, load_pct |
| crac | supply_temp, return_temp, fan_rpm, power_w, cooling_pct |

## MQTT topics

```
dc/{site}/{hall}/{rack}/{device}/{metric}
dc/dc1/hall-a/r01/srv-01/inlet_temp
dc/dc1/hall-a/hall/crac-1/supply_temp
```

Payload: `{"ts": 1790000000.0, "value": 23.4, "unit": "C"}` with `ts` in epoch seconds. Cooling units use the rack segment `hall`. The ingest path rejects unknown metrics, malformed payloads, bad topics and timestamps more than a day from the wall clock.

## Simulator

Racks hold servers, a top-of-rack switch with optical transceivers, and a PDU. CRAC units serve racks in an alternating pattern. Signals are coupled: rack load follows a diurnal curve, inlet temperature follows the serving CRAC supply temperature plus recirculation, outlet temperature follows server power over fan airflow with thermal lag, PDU power sums the devices behind it, and pre-FEC BER follows received optical power.

Injected faults ramp up, hold, and recover:

| fault | effect |
| --- | --- |
| `cooling_failure` | CRAC capacity drops, every rack it serves heats up |
| `fan_degradation` | one server loses airflow, fan rpm drops and outlet temperature climbs |
| `dirty_optics` | extra loss on a transceiver, rx power drops and BER climbs |
| `pdu_overload` | servers behind a PDU draw more than it is rated for |

```
python -m twin.simulator --host localhost --rate 5000 --faults 6
```

`--rate` caps messages per second and `--tick`, `--speed` control simulated time per tick. See `src/twin/simulator/README.md`.

## Setup

```
cp .env.example .env
make up
```

`make up` builds and starts postgres, mosquitto, the simulator, the Python ingest worker, the inference service, the API and the dashboard. Migrations run when the postgres volume is first created. To use Node-RED for ingestion instead of the Python worker, run `make up-nodered` (the compose profiles are `worker` and `nodered`).

| service | address |
| --- | --- |
| dashboard | http://localhost:8080 |
| API and docs | http://localhost:8000/docs |
| Node-RED editor | http://localhost:1880 |
| PostgreSQL | localhost:5432 |
| MQTT | localhost:1883 |

The inference service needs checkpoints in `./checkpoints`. Until they exist it logs that it is waiting.

Without Docker: `pip install -e ".[dev]"`, then `python -m twin.db.migrate`, `python -m twin.ingest.worker`, `python -m twin.simulator`, `uvicorn twin.api.main:app` and serve `dashboard/` with any static server (set `window.TWIN_API_BASE` and `window.TWIN_WS_BASE` if the API is on another origin).

## Training the models

```
python -m twin.simulator.export --hours 96 --faults 16 --out data/bench.csv
python -m twin.ml.train --task all --csv data/bench.csv --out checkpoints
python -m twin.ml.export checkpoints/thermal.pt
```

Training can read from PostgreSQL instead with `--dsn` (it uses the one-minute rollup). Each run writes `<task>.pt` and `<task>.metrics.json`. See `src/twin/ml/README.md` for the model, the windowing and the risk score.

## API

| method | path | description |
| --- | --- | --- |
| GET | `/api/sites`, `/api/racks`, `/api/devices` | fleet inventory, filter by hall, rack or device type |
| GET | `/api/devices/{site}/{hall}/{rack}/{device}` | one device |
| GET | `/api/topology` | nodes and dependency edges |
| GET | `/api/meta` | device types, metrics, thresholds |
| GET | `/api/telemetry/latest` | latest readings, filter by device, rack or metric |
| GET | `/api/telemetry/range` | raw points in a window |
| GET | `/api/telemetry/series` | downsampled avg, min and max, bucket widened to cap the point count |
| GET | `/api/health/racks`, `/api/health/offenders`, `/api/health/summary` | health analytics |
| GET | `/api/predictions` | latest forecast for a device and metric |
| GET | `/api/predictions/risk` | risk scores, filter by minimum risk |
| GET | `/api/alerts` | alerts, filter by status and severity |
| POST | `/api/alerts/{id}/ack`, `/api/alerts/{id}/resolve` | alert lifecycle |
| GET | `/api/rca` | stored analyses |
| POST | `/api/rca/analyze` | rank root causes for the open alerts |
| WS | `/ws/telemetry` | live readings, optional `device_key` and `metrics` query filters or JSON messages |

## Dashboard

Static files in `dashboard/`, served by nginx, which also proxies `/api/` and `/ws/` to the API. Plain ES modules, ApexCharts from a CDN.

- Overview: health KPIs, rack scores, top offenders, forecast risk.
- Telemetry: one device, any metric, history plus live WebSocket points with threshold lines.
- Forecasts: actual against forecast with the 95% band, risk breakdown, highest risk series.
- Alerts: filterable table with acknowledge and resolve, and the root cause panel.
- Topology: SVG rack grid per hall colored by health, cooling links on hover, rack detail on click.

## Root cause analysis

Alerts within 30 minutes of each other form an incident. Every alerting device and everything upstream of it becomes a candidate, scored on coverage, temporal precedence, precision and severity. See `src/twin/rca/README.md`.
