PY ?= .venv/bin/python

.PHONY: install backtest param report test clean init data ingest

install:
	uv pip install --python .venv/bin/python -e ".[dev]"

backtest:
	$(PY) -m ntquant.cli backtest

param:
	$(PY) -m ntquant.cli param

report:
	$(PY) -m ntquant.cli report

test:
	$(PY) -m pytest tests/

init:
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env from .env.example"; fi

data:
	$(PY) -m ntquant.cli backtest --catalog

ingest:
	$(PY) -m ntquant.cli ingest --source "$(source)" --config "$(config)"

clean:
	rm -rf output/* docs/data/*
