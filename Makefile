.PHONY: all test lint data

all: lint test

test:
	uv run pytest -v

lint:
	uv run ruff check

data:
	uv run python -m aideleg.acquire

.DELETE_ON_ERROR:
.PHONY: panel
panel: data/derived/aei_panel.parquet

data/derived/aei_panel.parquet: $(wildcard src/aideleg/aei/*.py) src/aideleg/aei/metric_map.csv data/raw/MANIFEST.json
	uv run python -m aideleg.aei
