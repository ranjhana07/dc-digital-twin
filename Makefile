PYTHON ?= python
HOURS ?= 72
RATE ?= 5000
COMPOSE = docker compose

.PHONY: install test test-js compile up up-nodered down logs migrate simulate export-data train export-models bench results clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest

test-js:
	node --test "dashboard/tests/*.test.mjs"

compile:
	$(PYTHON) -m compileall -q src benchmarks

up:
	$(COMPOSE) --profile worker up -d --build

up-nodered:
	$(COMPOSE) --profile nodered up -d --build

down:
	$(COMPOSE) --profile worker --profile nodered down

logs:
	$(COMPOSE) logs -f --tail=100

migrate:
	$(PYTHON) -m twin.db.migrate

simulate:
	$(PYTHON) -m twin.simulator --rate $(RATE)

export-data:
	$(PYTHON) -m twin.simulator.export --hours $(HOURS) --out data/telemetry.csv

train:
	$(PYTHON) -m twin.ml.train --task all --csv data/telemetry.csv --out checkpoints

export-models:
	for model in checkpoints/*.pt; do $(PYTHON) -m twin.ml.export $$model; done

bench:
	$(PYTHON) -m twin.simulator.export --hours 96 --faults 16 --out data/bench.csv
	$(PYTHON) -m twin.ml.train --task all --csv data/bench.csv --out checkpoints/bench --epochs 20 --patience 4 --hidden 32 --layers 1 --stride 6 --threads 1
	$(PYTHON) -m benchmarks.hardware
	$(PYTHON) -m benchmarks.simulator_bench
	$(PYTHON) -m benchmarks.forecast_report
	$(PYTHON) -m benchmarks.latency
	$(PYTHON) -m benchmarks.risk_eval
	$(PYTHON) -m benchmarks.rca_eval

results:
	$(PYTHON) -m benchmarks.render_results

clean:
	rm -rf data checkpoints .pytest_cache
