.PHONY: all test lint data

all: lint test

test:
	uv run pytest -v

lint:
	uv run ruff check

data:
	uv run python -m aideleg.acquire

.PHONY: panel
panel: data/derived/aei_panel.parquet

data/derived/aei_panel.parquet:
	uv run python -m aideleg.aei
