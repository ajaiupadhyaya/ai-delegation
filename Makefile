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
# the guard is the first prerequisite, so it fires before any rebuild of the exposure parquet
.PHONY: power power-unfrozen
power-unfrozen:
	@uv run python -c "import sys; from aideleg.market.seal import pap_frozen; \
		sys.exit('pap-v1 exists: the power analysis is frozen, not rerun' if pap_frozen() else 0)"

power: power-unfrozen data/derived/exposure_ff49.parquet
	uv run python -m aideleg.power

# regenerate the GENERATED blocks of PAP section 9 from the files (MANIFEST, code binding,
# frozen values)
.PHONY: freeze
freeze:
	uv run python scripts/pap_freeze.py

# P-RQ1 (PAP §0.5). The dry run scrambles every outcome before any estimator sees it and writes
# outside docs/results; it refuses if its directory already holds a run.
# It refuses while ${TMPDIR:-/tmp}/aideleg-rq1-dry exists, so delete that directory before a rerun
# (rm -rf "${TMPDIR:-/tmp}/aideleg-rq1-dry").
.PHONY: rq1-dry-run rq1-confirm
rq1-dry-run:
	uv run python -m aideleg.rq1.confirm --dry-run $${TMPDIR:-/tmp}/aideleg-rq1-dry

# SINGLE RUN, WRITE-ONCE: the logged first run of H1-H4 on real outcomes (plan 2 Task 11). It
# creates docs/results/rq1/confirmatory_rq1.attempt first and refuses forever after; never rerun.
rq1-confirm:
	uv run python -m aideleg.rq1.confirm

# RQ1/RQ2 reports (plan 2 Task 16). They read data/ and the committed confirmatory JSON; they never
# run the confirmatory runner and never touch the network. `results-rq1` rewrites everything in
# docs/results/rq1 except the four write-once confirmatory_rq1.* files.
.PHONY: results-rq1 results-rq2 results figures-check
results-rq1:
	uv run python -m aideleg.results.rq1

results-rq2:
	uv run python -m aideleg.results.rq2

results: results-rq1 results-rq2

# RQ3 (plan 3 Task 8): influence, events, terciles, fm, then summary.md. Exploratory and
# diagnostic outputs only; it never runs a confirmatory script.
.PHONY: rq3
rq3: data/derived/exposure_ff49.parquet
	uv run python -m aideleg.rq3 all

# H6 (plan 3 Task 12; PAP §6, D18; C-43). `h6-data` is the only H6 target that touches the
# network (SEC EDGAR); `h6` = build + talk + secondary + summary from saved raw files, offline.
.PHONY: h6-data h6
h6-data:
	uv run python -m aideleg.h6 acquire

h6: data/derived/exposure_ff49.parquet
	uv run python -m aideleg.h6 all

# Plan 4 robustness rows (PAP §8.2), offline: every Plan 4 row, then the appendix summary,
# implementation choices and forest figures. Never runs a confirmatory script or a network fetch;
# a reproduced CSV keeps its committed bytes (PAP §11 C-80).
.PHONY: robustness
robustness: data/derived/exposure_ff49.parquet
	uv run python -m aideleg.robustness --offline
	uv run python -m aideleg.robustness --summary

# fails if a figure has a PDF without a PNG, or the reverse
figures-check:
	@uv run python -c "from pathlib import Path; d = Path('docs/paper/figures'); \
		pdf = {p.stem for p in d.glob('*.pdf')}; png = {p.stem for p in d.glob('*.png')}; \
		odd = sorted(pdf ^ png); print('figures without a PDF/PNG twin:', odd) if odd else None; \
		raise SystemExit(1 if odd else 0)"

# the paper and the executive brief (Quarto; XeLaTeX for PDF). No code runs at render.
.PHONY: paper brief
paper:
	quarto render docs/paper --to pdf
	quarto render docs/paper --to html

brief:
	quarto render docs/paper/brief.qmd --to pdf
