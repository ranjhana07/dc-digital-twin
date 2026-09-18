# simulator

Models sites, halls, racks and devices and emits one reading per metric per tick.

- `signals.py` holds the pure signal functions (load curve, thermal, power, optics).
- `faults.py` describes injected faults and turns a schedule into per-device effects at a given time.
- `engine.py` steps the whole topology and returns `Reading` objects.
- `publisher.py` and `__main__.py` publish to MQTT. `export.py` writes the same data to CSV.

Faults: `cooling_failure` (CRAC capacity drops, every rack it serves heats up), `fan_degradation` (one server loses airflow), `dirty_optics` (extra loss on a transceiver, rx power drops and pre-FEC BER climbs), `pdu_overload` (servers behind a PDU draw more than the PDU is rated for).

```
python -m twin.simulator --host localhost --rate 5000 --faults 6
python -m twin.simulator.export --hours 72 --out data/telemetry.csv
```

`--rate` caps messages per second (0 paces by `--tick` and `--speed`).
