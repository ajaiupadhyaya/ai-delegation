"""The one door from Plan 4 to Plan 2 and Plan 3 code (the plan's "Upstream contract").

Every name is a re-export or a thin delegation; the adapter implements no estimator of its own
and never edits an upstream module. Its parity tests (`tests/robustness/test_upstream.py`) pin
it to the committed confirmatory and generated outputs.

Sources: Plan 2 — `results.common`, `rq1.*`, `describe.rq2`, `describe.anatomy`;
Plan 3 — `rq3.*` (guard, data, events, terciles, fama_macbeth, inference, report) and
`h6.*` (dictionary, edgar, talk).

AEI data are conversations matched to O*NET tasks.
"""

import json
from functools import cache
from typing import Literal

import polars as pl

from aideleg.config import DERIVED, ROOT
from aideleg.describe.anatomy import by_wage_decile
from aideleg.describe.rq2 import AEI_COLS, BENCH_COLS, bootstrap_indices, spearman_bootstrap
from aideleg.h6.dictionary import PRIMARY_TERMS, fts_phrases
from aideleg.h6.edgar import (
    FILERS,
    FORMS,
    denominator,
    fts_hits,
    hits_from_saved,
    numerator,
    saved_ranges,
)
from aideleg.h6.talk import T_YEAR, gap, gap_returns, spearman_ci, talk_table
from aideleg.results.common import FORBIDDEN_PHRASES, WORDING
from aideleg.rq1.confirm import Inputs, load_inputs
from aideleg.rq1.family import holm
from aideleg.rq1.h1h3 import estimate_h1, estimate_h3
from aideleg.rq1.h2 import build_h2_panel, estimate_h2
from aideleg.rq1.h4 import GeoSample, build_geo_sample, estimate_h4
from aideleg.rq1.inputs import task_families, two_month_mean
from aideleg.rq1.result import Coef, HypothesisResult
from aideleg.rq1.rows import TaskRows, build_task_rows
from aideleg.rq3.data import exposures, zero_assigned
from aideleg.rq3.events import EVENTS, Event, run_events
from aideleg.rq3.fama_macbeth import run_fm
from aideleg.rq3.guard import ConfirmatoryNotRecorded, assert_confirmatory_recorded
from aideleg.rq3.inference import vector_test
from aideleg.rq3.report import zero_assigned_lines
from aideleg.rq3.terciles import WINDOWS, run_terciles

RESULTS = ROOT / "docs/results"
RQ1_DIR = RESULTS / "rq1"
RQ2_DIR = RESULTS / "rq2"
RQ3_DIR = RESULTS / "rq3"
H6_DIR = RESULTS / "h6"
# Untracked: the `out_dir` of Plan 3's `run_*` for variant runs; nothing here is committed.
WORK_DIR = DERIVED / "robustness"

RQ3_EXPO_COLUMNS = ("design", "ff49", "ff49_short", "z_delegation", "z_usage", "z_aioe")
RQ3_DESIGNS = ("A_r2", "A_pooled", "B")


@cache
def rq1_inputs() -> Inputs:
    """Plan 2's study inputs (`rq1.confirm.load_inputs`), loaded once per process."""
    return load_inputs()


def task_rows(
    *,
    release: str = "r6",
    source: str = "claude_ai",
    family_level: Literal["iwa", "gwa", "dwa"] = "iwa",
) -> TaskRows:
    """The H1/H3 rows from Plan 2's `build_task_rows` on the study inputs."""
    inp = rq1_inputs()
    return build_task_rows(
        inp.panel,
        inp.index,
        task_families(family_level),
        inp.wages,
        inp.oews_codes,
        inp.soc_structure,
        release=release,
        source=source,
        family_level=family_level,
    )


def h2_panel(**kw) -> pl.DataFrame:
    """Plan 2's `build_h2_panel` on the study panel; keywords pass through."""
    return build_h2_panel(rq1_inputs().panel, **kw)


def geo_sample(**kw) -> GeoSample:
    """Plan 2's `build_geo_sample` on the study panel. At country level the r3 GDP/WAP files
    are passed, as `confirm.run` does; at `us_state` level the builder reads its own files."""
    inp = rq1_inputs()
    if kw.get("geo", "country") == "country":
        kw.setdefault("gdp", inp.gdp_country)
        kw.setdefault("wap", inp.wap_country)
    return build_geo_sample(inp.panel, **kw)


def load_filers() -> pl.DataFrame:
    """The H6 filer frame written by Plan 3's `h6 build`."""
    return pl.read_parquet(FILERS)


def committed_rq1() -> dict:
    """Plan 2's committed P-RQ1 record."""
    return json.loads((RQ1_DIR / "confirmatory_rq1.json").read_text(encoding="utf-8"))


def rq2_correlations(exposure: pl.DataFrame, bench: pl.DataFrame) -> pl.DataFrame:
    """Plan 2's Design B could-vs-does Spearman table for one FF49 exposure frame.

    Joined as `results.rq2.could_vs_does` joins (inner on `ff49`, exposure order kept), with
    the Design B draws of `bootstrap_indices` (the first drawn from the seeded generator)."""
    df = exposure.join(bench.select("ff49", *BENCH_COLS), on="ff49", how="inner")
    pairs = [(a, b) for a in AEI_COLS for b in BENCH_COLS]
    return spearman_bootstrap(df, pairs, bootstrap_indices(df.height, designs=("B",))["B"])


def to_rq3_expo(variant: pl.DataFrame, design: Literal["A_r2", "A_pooled", "B"]) -> pl.DataFrame:
    """A variant FF49 frame (`industry`, `industry_short`, z columns) as Plan 3's exposure
    frame `design, ff49, ff49_short, z_delegation, z_usage, z_aioe`."""
    if design not in RQ3_DESIGNS:
        raise ValueError(f"design must be one of {RQ3_DESIGNS}, got {design!r}")
    return variant.rename({"industry": "ff49", "industry_short": "ff49_short"}).select(
        pl.lit(design).alias("design"), *RQ3_EXPO_COLUMNS[1:]
    )


__all__ = [
    "AEI_COLS",
    "BENCH_COLS",
    "EVENTS",
    "FORBIDDEN_PHRASES",
    "FORMS",
    "H6_DIR",
    "PRIMARY_TERMS",
    "RQ1_DIR",
    "RQ2_DIR",
    "RQ3_DIR",
    "T_YEAR",
    "WINDOWS",
    "WORDING",
    "WORK_DIR",
    "Coef",
    "ConfirmatoryNotRecorded",
    "Event",
    "GeoSample",
    "HypothesisResult",
    "Inputs",
    "TaskRows",
    "assert_confirmatory_recorded",
    "bootstrap_indices",
    "build_geo_sample",
    "build_h2_panel",
    "build_task_rows",
    "by_wage_decile",
    "committed_rq1",
    "denominator",
    "estimate_h1",
    "estimate_h2",
    "estimate_h3",
    "estimate_h4",
    "exposures",
    "fts_hits",
    "fts_phrases",
    "gap",
    "gap_returns",
    "geo_sample",
    "h2_panel",
    "hits_from_saved",
    "holm",
    "load_filers",
    "numerator",
    "rq1_inputs",
    "rq2_correlations",
    "run_events",
    "run_fm",
    "run_terciles",
    "saved_ranges",
    "spearman_bootstrap",
    "spearman_ci",
    "talk_table",
    "task_families",
    "task_rows",
    "to_rq3_expo",
    "two_month_mean",
    "vector_test",
    "zero_assigned",
    "zero_assigned_lines",
]
