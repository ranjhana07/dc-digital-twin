PYTHON ?= python
HOURS ?= 72
RATE ?= 5000
COMPOSE = docker compose

.PHONY: install test test-js compile up up-nodered down logs migrate simulate export-data train export-models clean

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

clean:
	rm -rf data checkpoints .pytest_cache
