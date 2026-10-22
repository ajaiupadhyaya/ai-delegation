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

.PHONY: exposure
exposure: data/derived/exposure_ff49.parquet

# one recipe writes both exposure_occupation.parquet and exposure_ff49.parquet
data/derived/exposure_ff49.parquet: src/aideleg/exposure.py src/aideleg/occupations.py \
		src/aideleg/aei/tasks.py src/aideleg/acquire/sources.py \
		$(wildcard src/aideleg/bls/*.py) $(wildcard src/aideleg/crosswalk/*.py) \
		data/raw/MANIFEST.json data/derived/aei_panel.parquet
	uv run python -m aideleg.exposure
