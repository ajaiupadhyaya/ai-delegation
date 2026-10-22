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

# every derived file also depends on the shared config, the source registry and the French reader
COMMON := src/aideleg/config.py src/aideleg/acquire/sources.py src/aideleg/market/french.py

data/derived/aei_panel.parquet: $(wildcard src/aideleg/aei/*.py) src/aideleg/aei/metric_map.csv \
		$(COMMON) data/raw/MANIFEST.json
	uv run python -m aideleg.aei

.PHONY: exposure
exposure: data/derived/exposure_ff49.parquet

# one recipe writes both exposure_occupation.parquet and exposure_ff49.parquet
data/derived/exposure_ff49.parquet: src/aideleg/exposure.py src/aideleg/occupations.py \
		src/aideleg/aei/tasks.py $(COMMON) \
		$(wildcard src/aideleg/bls/*.py) $(wildcard src/aideleg/crosswalk/*.py) \
		data/raw/MANIFEST.json data/derived/aei_panel.parquet
	uv run python -m aideleg.exposure

.PHONY: benchmarks
benchmarks: data/derived/benchmark_ff49.parquet

data/derived/benchmark_ff49.parquet: src/aideleg/benchmarks.py src/aideleg/exposure.py $(COMMON) \
		$(wildcard src/aideleg/bls/*.py) $(wildcard src/aideleg/crosswalk/*.py) \
		data/raw/MANIFEST.json data/derived/exposure_ff49.parquet
	uv run python -m aideleg.benchmarks

# coverage tables only (no H1-H4 relationships, no market data); always regenerated
.PHONY: audit
audit: data/derived/aei_panel.parquet data/derived/exposure_ff49.parquet \
		data/derived/benchmark_ff49.parquet
	uv run python -m aideleg.audit

# pre-seal power analysis for H5/H5b (returns end 2022-11-29); rewrites the generated block.
# Pre-seal only: once the tag pap-v1 exists the frozen values are fixed, and both this guard
# and `aideleg.power.main` refuse. (The benchmarks are computed in-process, not read from
# their parquet.)
.PHONY: power
power: data/derived/exposure_ff49.parquet
	@uv run python -c "import sys; from aideleg.market.seal import pap_frozen; \
		sys.exit('pap-v1 exists: the power analysis is frozen, not rerun' if pap_frozen() else 0)"
	uv run python -m aideleg.power

# regenerate the GENERATED blocks of PAP section 9 from the files (MANIFEST, code binding,
# frozen values)
.PHONY: freeze
freeze:
	uv run python scripts/pap_freeze.py
