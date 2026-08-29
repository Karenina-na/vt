PY ?= .venv/bin/python

.PHONY: install backtest param report test clean init data ingest init-config

install:
	uv pip install --python .venv/bin/python -e ".[dev]"

backtest:
	$(PY) run.py backtest

param:
	$(PY) run.py param

report:
	$(PY) run.py report

test:
	$(PY) -m pytest tests/

init:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi

init-config:
	@if [ ! -f configs/backtest.yaml ]; then cp configs/backtest.example.yaml configs/backtest.yaml; echo "Created configs/backtest.yaml"; fi
	@if [ ! -f configs/param.yaml ]; then cp configs/param.example.yaml configs/param.yaml; echo "Created configs/param.yaml"; fi

data:
	$(PY) run.py backtest --catalog

ingest:
	$(PY) run.py ingest --source "$(source)" --config "$(config)"

clean:
	rm -rf output/* docs/data/*