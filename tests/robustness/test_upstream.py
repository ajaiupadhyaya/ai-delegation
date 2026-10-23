"""The upstream adapter: parity with the committed Plan 2 and Plan 3 outputs (same code, same
inputs, rel = 1e-12), and an import scan that keeps the adapter a pure re-export layer."""

import ast
import json
import math
import sys
from pathlib import Path

import polars as pl
import pytest

from aideleg.config import DERIVED, ROOT
from aideleg.robustness import upstream as up

REL = 1e-12
UPSTREAM_PY = ROOT / "src/aideleg/robustness/upstream.py"


def _close(a, b) -> None:
    if a is None or b is None:
        assert a is None and b is None, (a, b)
    elif isinstance(a, float) or isinstance(b, float):
        assert a == pytest.approx(b, rel=REL, abs=0.0), (a, b)
    else:
        assert a == b, (a, b)


def _frames_equal(got: pl.DataFrame, want: pl.DataFrame) -> None:
    """Same columns and rows, in order; floats at rel = 1e-12, everything else exact."""
    assert got.columns == want.columns
    assert got.height == want.height
    for c in want.columns:
        g, w = got[c].to_list(), want[c].to_list()
        for i, (x, y) in enumerate(zip(g, w, strict=True)):
            if isinstance(x, float) or isinstance(y, float):
                if x is None or y is None:
                    assert x is None and y is None, (c, i, x, y)
                else:
                    assert x == pytest.approx(y, rel=REL, abs=0.0), (c, i, x, y)
            else:
                assert str(x) == str(y), (c, i, x, y)


def _check_coefs(res, committed: dict, names) -> None:
    for n in names:
        c, w = res.coefs[n], committed["coefs"][n]
        for f in ("estimate", "se", "p"):
            _close(getattr(c, f), w[f])
    _close(res.p_family, committed["p_family"])


@pytest.mark.data
def test_h1_h3_reproduce_committed():
    committed = up.committed_rq1()["results"]
    tr = up.task_rows()
    for h, est in (("H1", up.estimate_h1), ("H3", up.estimate_h3)):
        res = est(tr)
        assert set(res.coefs) == set(committed[h]["coefs"])
        _check_coefs(res, committed[h], committed[h]["coefs"])


@pytest.mark.data
def test_h2_reproduces_committed():
    committed = up.committed_rq1()["results"]["H2"]
    res = up.estimate_h2(up.h2_panel())
    _check_coefs(res, committed, ["trend"])
    _close(res.diagnostics["p_wild"], committed["diagnostics"]["p_wild"])
    assert res.diagnostics["n_wild_draws"] == 1296


@pytest.mark.data
def test_h4_reproduces_committed():
    committed = up.committed_rq1()["results"]["H4"]
    res = up.estimate_h4(up.geo_sample().frame)
    for n in ("log_aui", "log_income"):
        _close(res.coefs[n].estimate, committed["coefs"][n]["estimate"])
    _close(res.diagnostics["F"], committed["diagnostics"]["F"])
    # PAP §11 C-32 / C-69: H4's `mix` is order-dependent at ~1e-14, which moves a p of 4.8e-24
    # by ~1e-12 relative; -log10 p spreads ~1e-14 relative, so this is an equality check.
    _close(-math.log10(res.p_family), -math.log10(committed["p_family"]))


@pytest.mark.data
def test_rq2_reproduces_committed():
    # The FF49 benchmark frame of could_vs_does.csv: Plan 1's `aideleg.benchmarks.benchmark_ff49`
    # (`make benchmarks` writes it to data/derived/benchmark_ff49.parquet, which Plan 2 reads).
    from aideleg.benchmarks import benchmark_ff49
    from aideleg.results.common import round10

    expo_b = pl.read_parquet(DERIVED / "exposure_ff49.parquet").filter(pl.col("design") == "B")
    got = up.rq2_correlations(expo_b, benchmark_ff49())
    assert got.columns == ["aei", "benchmark", "n", "spearman", "ci_low", "ci_high", "n_draws_used"]
    want = (
        pl.read_csv(up.RQ2_DIR / "could_vs_does.csv").filter(pl.col("design") == "B").drop("design")
    )
    # Plan 2 writes the CSV through `round10` (10 significant digits): compare like with like.
    _frames_equal(round10(got), want)


@pytest.mark.data
def test_terciles_reproduce_committed(tmp_path: Path):
    got = up.run_terciles(tmp_path)
    want = pl.read_csv(up.RQ3_DIR / "terciles.csv")
    _frames_equal(got, want)
    assert not (tmp_path / "fig_rq3_tercile_cumulative.pdf").exists()


@pytest.mark.data
def test_event_slopes_reproduce_committed(tmp_path: Path):
    got = up.run_events(tmp_path)
    want = pl.read_csv(up.RQ3_DIR / "event_study.csv", try_parse_dates=True)
    _frames_equal(got, want)
    chat = got.filter((pl.col("event") == "ChatGPT") & (pl.col("horizon") == 5))
    assert "A_r2" in chat["design"].to_list()


@pytest.mark.data
def test_h6_talk_reproduces_committed(monkeypatch):
    from aideleg.h6 import edgar

    def _no_network(*a, **k):
        pytest.fail("the H6 parity read touched the network")

    for name in ("fts_source", "_get_json", "fts_hits", "acquire_fts"):
        monkeypatch.setattr(edgar, name, _no_network)
    filers = up.load_filers()
    t = up.talk_table(up.numerator(up.hits_from_saved(), filers), up.denominator(filers))
    got = t.filter(pl.col("year") == 2024)
    want = pl.read_csv(up.H6_DIR / "talk_index.csv").filter(pl.col("year") == 2024)
    assert got.height == want.height == 50
    _frames_equal(got, want)


def test_adapter_paths_and_reexports():
    assert up.RQ1_DIR == ROOT / "docs/results/rq1"
    assert up.RQ2_DIR == ROOT / "docs/results/rq2"
    assert up.RQ3_DIR == ROOT / "docs/results/rq3"
    assert up.H6_DIR == ROOT / "docs/results/h6"
    assert up.WORK_DIR == DERIVED / "robustness"
    names = [
        "assert_confirmatory_recorded",
        "ConfirmatoryNotRecorded",
        "WORDING",
        "FORBIDDEN_PHRASES",
        "build_task_rows",
        "TaskRows",
        "task_families",
        "two_month_mean",
        "estimate_h1",
        "estimate_h3",
        "build_h2_panel",
        "estimate_h2",
        "build_geo_sample",
        "estimate_h4",
        "holm",
        "HypothesisResult",
        "Coef",
        "spearman_bootstrap",
        "bootstrap_indices",
        "by_wage_decile",
        "Event",
        "EVENTS",
        "run_events",
        "run_terciles",
        "run_fm",
        "WINDOWS",
        "vector_test",
        "exposures",
        "zero_assigned",
        "zero_assigned_lines",
        "PRIMARY_TERMS",
        "fts_phrases",
        "fts_hits",
        "hits_from_saved",
        "saved_ranges",
        "numerator",
        "denominator",
        "FORMS",
        "talk_table",
        "gap",
        "spearman_ci",
        "gap_returns",
        "T_YEAR",
        "rq1_inputs",
        "task_rows",
        "h2_panel",
        "geo_sample",
        "load_filers",
        "committed_rq1",
        "rq2_correlations",
        "to_rq3_expo",
    ]
    missing = [n for n in names if not hasattr(up, n)]
    assert not missing, missing
    assert set(names) <= set(up.__all__)


def test_to_rq3_expo_renames_variant_columns():
    v = pl.DataFrame(
        {
            "industry": [1, 2],
            "industry_short": ["Agric", "Food"],
            "z_delegation": [0.5, -0.5],
            "z_usage": [1.0, -1.0],
            "z_aioe": [0.1, -0.1],
            "extra": [9, 9],
        }
    )
    out = up.to_rq3_expo(v, "A_r2")
    assert out.columns == ["design", "ff49", "ff49_short", "z_delegation", "z_usage", "z_aioe"]
    assert out["design"].to_list() == ["A_r2", "A_r2"]
    assert out["ff49"].to_list() == [1, 2]
    with pytest.raises(ValueError):
        up.to_rq3_expo(v, "C")


def test_adapter_imports_only_upstream():
    allowed_aideleg = {
        "aideleg.config",
        "aideleg.rq1",
        "aideleg.describe",
        "aideleg.results",
        "aideleg.rq3",
        "aideleg.h6",
    }
    third = {"polars", "numpy", "scipy", "statsmodels"}
    tree = ast.parse(UPSTREAM_PY.read_text(encoding="utf-8"))
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative import in the adapter"
            mods = [node.module or ""]
        else:
            continue
        for m in mods:
            top = m.split(".")[0]
            if top == "aideleg":
                if not any(m == a or m.startswith(a + ".") for a in allowed_aideleg):
                    bad.append(m)
                if m.startswith("aideleg.robustness"):
                    bad.append(m)
            elif top not in third and top not in sys.stdlib_module_names:
                bad.append(m)
    assert not bad, bad
    # No estimator of its own: every function body is a short delegation.
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            assert len(node.body) <= 12, node.name


def test_committed_rq1_is_the_json():
    assert up.committed_rq1() == json.loads(
        (ROOT / "docs/results/rq1/confirmatory_rq1.json").read_text(encoding="utf-8")
    )
