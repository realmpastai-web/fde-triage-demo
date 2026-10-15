.PHONY: install demo run serve test lint typecheck eval gate check data docker clean

PY ?= python3

install:            ## install the package and dev tools
	$(PY) -m pip install -e ".[dev]"

demo: install run eval serve   ## one command: install, triage the export, run evals, open the dashboard

run:                ## ingest data/raw and triage everything into the approval queue
	$(PY) -m triage run --reset

serve:              ## API + dashboard on http://127.0.0.1:8000
	$(PY) -m triage serve --host 0.0.0.0 --port 8000

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m ruff check .
	$(PY) -m ruff format --check src tests

typecheck:
	$(PY) -m mypy

eval:               ## write reports/eval_report.{md,json}
	$(PY) -m triage eval

gate:               ## eval + fail on regression against evals/thresholds.json (what CI runs)
	$(PY) -m triage eval --gate evals/thresholds.json

check: lint typecheck test gate   ## everything CI checks

data:               ## regenerate the synthetic client export and labelled sets
	$(PY) scripts/generate_data.py
	cd scripts && $(PY) golden_source.py && $(PY) holdout_source.py

docker:
	docker compose up --build

clean:
	rm -rf var reports/*.json .pytest_cache .mypy_cache .ruff_cache
