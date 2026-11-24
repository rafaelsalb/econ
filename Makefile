PY ?= .venv/bin/python

.PHONY: ingest backtest score loop loop-agents report test check pipeline all agents \
        ensemble lockbox-open lockbox-status final-report phase3 \
        sandbox-build sandbox-setup sandbox-smoke clean gate dev-check dev-list \
        dev-dashboard dev-smoke

ingest:
	$(PY) -m econ.cli ingest

backtest:
	$(PY) -m econ.cli backtest --models all --start 2010-01-01 --end 2019-12-31

score:
	$(PY) -m econ.cli score

loop:
	$(PY) -m econ.cli loop --model new_keynesian

loop-agents:
	$(PY) -m econ.cli loop --model new_keynesian --agents

report:
	$(PY) -m econ.cli report

ensemble:
	$(PY) -m econ.cli ensemble

lockbox-open:
	$(PY) -m econ.cli lockbox open

lockbox-status:
	$(PY) -m econ.cli lockbox status

final-report:
	$(PY) -m econ.cli final-report

phase3: ensemble lockbox-open final-report

test:
	$(PY) -m pytest -q

check:
	$(PY) -m econ.cli check

agents:
	$(PY) -m econ.cli agents render
	$(PY) -m econ.cli agents check
	$(PY) -m econ.cli dev agents render
	$(PY) -m econ.cli dev agents check

dev-check:
	$(PY) -m econ.cli dev doctor
	$(PY) -m econ.cli dev validate --all
	$(PY) -m econ.cli dev agents check

dev-list:
	$(PY) -m econ.cli dev list

dev-dashboard:
	$(PY) -m econ.cli dev report --write

dev-smoke:
	$(PY) -m econ.cli dev smoke --fake

dev-daemon:
	$(PY) -m econ.cli dev daemon --once --max-parallel 2

dev-maintenance:
	$(PY) -m econ.cli dev maintenance

gate: test check agents dev-check
	@echo "GATE PASS"

sandbox-build:
	$(PY) -m econ.cli sandbox build

sandbox-setup:
	$(PY) -m econ.cli sandbox setup

sandbox-smoke:
	$(PY) -m econ.cli sandbox smoke

pipeline: backtest score ensemble

all: test check

clean:
	rm -rf .pytest_cache .mypy_cache .ruff_cache
