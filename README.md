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

## Results

Every number below comes from a script in `benchmarks/` and the raw output is committed in `results/`. `make bench` regenerates them and `make results` prints the tables below. Nothing here comes from a live Postgres or MQTT broker.

How the numbers were produced:

- Data: `python -m twin.simulator.export --hours 96 --faults 16 --out data/bench.csv`, 2 halls with 6 racks each, one sample per minute.
- Models: `python -m twin.ml.train --task all --csv data/bench.csv --out checkpoints/bench --epochs 20 --patience 4 --hidden 32 --layers 1 --stride 6 --threads 1`. Windows are 60 minutes in, 30 minutes out. The test set is the last 15% of each device's series.
- Forecast errors are in the metric's own unit. BER is evaluated in log10 space. The baseline is persistence, the last observed value repeated over the horizon. `results/forecast_summary.csv` also holds MAPE.
- Risk detection and RCA use fresh simulations with different seeds from the training data. `benchmarks/risk_eval.py` and `benchmarks/rca_eval.py` document how positives and ground truth are defined.
- The machine was busy with other processes during these runs, so the timing numbers are likely worse than an idle machine would give.

Measured on 13th Gen Intel(R) Core(TM) i5-13420H (12 logical cores), Windows 11 (10.0.26200), Python 3.12.10, torch 2.15.0+cpu (CPU).

### Simulator throughput

| racks | devices | stage | readings | seconds | readings/s |
| --- | --- | --- | --- | --- | --- |
| 12 | 100 | step | 256800 | 0.757 | 339,399 |
| 12 | 100 | step+topic+payload | 256800 | 3.204 | 80,155 |
| 48 | 392 | step | 1003200 | 3.622 | 276,950 |
| 48 | 392 | step+topic+payload | 1003200 | 13.665 | 73,416 |

### Forecast accuracy

| task | target | GRU MAE | persistence MAE | MAE change | GRU RMSE | persistence RMSE | RMSE change | test windows |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ber | rx_power_dbm | 0.0636 | 0.0778 | -18.2% | 0.2756 | 0.2814 | -2.1% | 3120 |
| ber | pre_fec_ber | 0.1432 | 0.1804 | -20.6% | 0.2335 | 0.2686 | -13.1% | 3120 |
| power | power_w | 44.8528 | 48.9548 | -8.4% | 69.8703 | 74.6268 | -6.4% | 1560 |
| power | load_pct | 1.8699 | 2.0398 | -8.3% | 2.9141 | 3.1095 | -6.3% | 1560 |
| thermal | inlet_temp | 0.2454 | 0.285 | -13.9% | 0.307 | 0.3576 | -14.1% | 6240 |
| thermal | outlet_temp | 0.2537 | 0.2799 | -9.4% | 0.3754 | 0.4078 | -8.0% | 6240 |

By horizon:

| task | target | horizon | GRU MAE | persistence MAE | GRU RMSE | persistence RMSE |
| --- | --- | --- | --- | --- | --- | --- |
| ber | rx_power_dbm | 5 min | 0.0488 | 0.0545 | 0.1325 | 0.1356 |
| ber | rx_power_dbm | 15 min | 0.0669 | 0.0827 | 0.295 | 0.3007 |
| ber | rx_power_dbm | 30 min | 0.08 | 0.1016 | 0.4246 | 0.4323 |
| ber | pre_fec_ber | 5 min | 0.1237 | 0.1382 | 0.1692 | 0.1855 |
| ber | pre_fec_ber | 15 min | 0.1503 | 0.1919 | 0.2457 | 0.286 |
| ber | pre_fec_ber | 30 min | 0.161 | 0.2193 | 0.3011 | 0.3503 |
| power | power_w | 5 min | 34.2225 | 36.3179 | 46.3452 | 48.2922 |
| power | power_w | 15 min | 47.6791 | 52.3279 | 73.2247 | 78.2722 |
| power | power_w | 30 min | 55.7895 | 61.8769 | 93.6435 | 101.5821 |
| power | load_pct | 5 min | 1.4267 | 1.5133 | 1.9388 | 2.0122 |
| power | load_pct | 15 min | 1.9897 | 2.1803 | 3.0569 | 3.2613 |
| power | load_pct | 30 min | 2.3282 | 2.5782 | 3.8966 | 4.2326 |
| thermal | inlet_temp | 5 min | 0.2203 | 0.2446 | 0.274 | 0.3065 |
| thermal | inlet_temp | 15 min | 0.2586 | 0.3049 | 0.3208 | 0.382 |
| thermal | inlet_temp | 30 min | 0.2727 | 0.3145 | 0.3436 | 0.3982 |
| thermal | outlet_temp | 5 min | 0.1866 | 0.1951 | 0.2487 | 0.2589 |
| thermal | outlet_temp | 15 min | 0.2748 | 0.3048 | 0.4032 | 0.4401 |
| thermal | outlet_temp | 30 min | 0.3199 | 0.3586 | 0.5032 | 0.5521 |

Training:

| task | epochs run | train seconds | best val loss |
| --- | --- | --- | --- |
| ber | 12 | 114.4 | 0.16127 |
| power | 20 | 99.1 | 0.05374 |
| thermal | 8 | 136.8 | 0.10324 |

### Inference latency

Torch threads: 1.

| task | engine | batch | p50 ms | p95 ms | ms per series |
| --- | --- | --- | --- | --- | --- |
| thermal | eager | 1 | 4.647 | 13.679 | 4.647 |
| thermal | eager | 16 | 5.837 | 24.918 | 0.3648 |
| thermal | eager | 64 | 10.261 | 19.46 | 0.1603 |
| thermal | eager | 256 | 28.071 | 40.721 | 0.1097 |
| thermal | torchscript | 1 | 4.316 | 10.39 | 4.316 |
| thermal | torchscript | 16 | 6.251 | 13.23 | 0.3907 |
| thermal | torchscript | 64 | 10.29 | 19.449 | 0.1608 |
| thermal | torchscript | 256 | 27.741 | 46.096 | 0.1084 |
| power | eager | 1 | 4.417 | 9.112 | 4.417 |
| power | eager | 16 | 5.632 | 10.903 | 0.352 |
| power | eager | 64 | 11.311 | 22.778 | 0.1767 |
| power | eager | 256 | 26.006 | 43.75 | 0.1016 |
| power | torchscript | 1 | 4.497 | 11.072 | 4.497 |
| power | torchscript | 16 | 5.009 | 10.699 | 0.3131 |
| power | torchscript | 64 | 9.198 | 18.919 | 0.1437 |
| power | torchscript | 256 | 28.498 | 51.731 | 0.1113 |
| ber | eager | 1 | 4.303 | 7.691 | 4.303 |
| ber | eager | 16 | 6.189 | 17.146 | 0.3868 |
| ber | eager | 64 | 12.358 | 37.695 | 0.1931 |
| ber | eager | 256 | 25.428 | 34.576 | 0.0993 |
| ber | torchscript | 1 | 4.579 | 9.271 | 4.579 |
| ber | torchscript | 16 | 6.578 | 11.413 | 0.4111 |
| ber | torchscript | 64 | 11.508 | 31.956 | 0.1798 |
| ber | torchscript | 256 | 25.831 | 39.261 | 0.1009 |

Full thermal cycle (assemble windows, two forecasts per device, risk and alert specs, in-memory store):

| devices | p50 ms | p95 ms | ms per device |
| --- | --- | --- | --- |
| 16 | 123.049 | 159.041 | 7.6905 |
| 64 | 537.211 | 628.395 | 8.3939 |
| 256 | 2689.702 | 3392.001 | 10.5066 |

### Risk detection

48 simulated hours, 8 injected faults, 6 racks, seed 101, alert at risk >= 0.5 or a current threshold breach.

- Sample level: precision 1.0, recall 0.4618, F1 0.6318 (TP 1970, FP 0, FN 2296, TN 215694).
- Fault level: 8 of 8 faults raised an alert on an affected series during the fault.
- No forecast-only alert fired before a threshold breach on an affected series.

| fault kind | faults | detected | median delay after onset (min) |
| --- | --- | --- | --- |
| cooling_failure | 2 | 2 | 5.1 |
| fan_degradation | 2 | 2 | 10.0 |
| dirty_optics | 2 | 2 | 6.050000000000001 |
| pdu_overload | 2 | 2 | 4.95 |

### Root cause ranking

Single fault, 200 incidents: top-1 1.0, top-3 1.0.

| fault kind | incidents | top-1 | top-3 |
| --- | --- | --- | --- |
| cooling_failure | 50 | 50 | 50 |
| fan_degradation | 50 | 50 | 50 |
| dirty_optics | 50 | 50 | 50 |
| pdu_overload | 50 | 50 | 50 |

Two concurrent faults, 100 incidents: top-1 is a true cause in 1.0 of them, both true causes within the top 3 in 0.61.


## Project layout

```
db/migrations/        SQL migrations
dashboard/            static frontend, nginx.conf, node tests
docker/               Dockerfiles for the Python services and the dashboard
ingest/               mosquitto config and the Node-RED flow
src/twin/common/      settings, metric catalog, topics, payloads, topology
src/twin/simulator/   signal models, faults, engine, MQTT publisher, CSV export
src/twin/ingest/      validation, batcher, Postgres sink, worker
src/twin/db/          migration runner, topology sync
src/twin/ml/          datasets, GRU model, training, evaluation, export, risk, inference
src/twin/rca/         asset graph and root cause ranking
src/twin/api/         FastAPI app, routers, health scoring, SQL repository
benchmarks/           scripts that produce the files in results/
results/              raw output of the benchmark scripts
tests/                pytest suite
```

## Testing

```
make test
make test-js
```

The Python tests cover topic parsing, signal models and fault injection, batching, windowing and scaling, GRU shapes (skipped without torch), risk scoring, the inference loop against a fake store, RCA ranking on a small synthetic topology, and every API route against an in-memory repository. None of them need Postgres, MQTT or network access. The SQL repository itself is only checked for protocol coverage and query compilation, since it needs a live database.

## Not verified here

The Compose stack, the Node-RED flow, the Postgres migrations, the SQL repository and the MQTT publisher were written to be run with Docker, Postgres and a broker, none of which were available while developing this. They are untested end to end.

`benchmarks/ingest_bench.py` measures `COPY` against `execute_values` insert throughput into a live `telemetry` table (`python -m benchmarks.ingest_bench --dsn postgresql://twin:twin@localhost:5432/twin`). No ingestion numbers are reported above because it has not been run.
