"""Data audit: table rendering and the integrity constraint (no H1-H4 relationships)."""

import ast
import re
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg import audit
from aideleg.config import DERIVED, RAW

SOURCE = Path(audit.__file__).read_text()


def test_md_table_formats_nulls_floats_and_lists():
    df = pl.DataFrame({"a": ["x|y", None], "b": [1.23456, None], "c": [[1, 2], []]},
                      schema={"a": pl.String, "b": pl.Float64, "c": pl.List(pl.Int64)})
    out = audit.md_table(df, digits={"b": 3}).splitlines()
    assert out[0] == "| a | b | c |"
    assert out[2] == "| x/y | 1.235 | 1, 2 |"
    assert out[3] == "| — | — | — |"


def test_write_doc_carries_wording_rule(tmp_path):
    p = audit.write_doc("t", "Title", [("H", "body")], out=tmp_path)
    text = p.read_text()
    assert "conversations matched to O*NET tasks" in text
    assert "Do not edit by hand" in text and "## H" in text


# Integrity constraint (global constraints): audit.py must not touch the H1-H4 covariates
# (wages, education, error cost, country covariates) or market returns.
FORBIDDEN = ["a_median", "wage", "education", "error_cost", "gdp", "working_age",
             "usage_per_capita", "french", "returns", "factor"]


@pytest.mark.parametrize("token", FORBIDDEN)
def test_audit_source_has_no_hypothesis_covariates(token):
    code = "\n".join(line for line in SOURCE.splitlines()
                     if not line.lstrip().startswith("#"))
    tree = ast.parse(code)
    doc = ast.get_docstring(tree) or ""
    body = code.replace(doc, "")  # the module docstring states the rule itself
    assert re.search(token, body, flags=re.IGNORECASE) is None, token


def test_audit_imports_no_market_module():
    tree = ast.parse(SOURCE)
    mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | {
        a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(m and m.startswith("aideleg.market") for m in mods), mods


def test_task_collab_suppression_toy():
    rows = []
    for node, pct, auto, n in [("1", 60.0, 50.0, 5), ("2", 40.0, 100.0, 1)]:
        rows.append((node, "pct", pct))
        rows.append((node, "automation_pct", auto))
        for p in audit.PATTERNS[:n]:
            rows.append((node, p, 100.0 / n))
        rows += [(node, "not_classified_pct", 10.0), (node, "none_pct", 0.0)]
    rows.append(("overall", "automation_pct", 55.0))
    panel = pl.DataFrame({
        "release": "r3", "source": "claude_ai", "period_start": date(2025, 8, 4),
        "geo_level": "global",
        "taxonomy": ["overall" if r[0] == "overall" else "onet_task" for r in rows],
        "node_id": [r[0] for r in rows], "metric": [r[1] for r in rows],
        "value": [r[2] for r in rows]})
    out = audit.task_collab_suppression(panel).row(0, named=True)
    assert out["with_all_five"] == 1 and out["tasks"] == 2
    assert out["weighted_task_automation"] == pytest.approx(70.0)
    assert out["auto_partial_tasks"] == pytest.approx(100.0)
    assert out["partial_tasks_pct_mass"] == pytest.approx(40.0)
    assert out["weighted_suppressed_pct"] == pytest.approx(10.0)
    assert out["gap"] == pytest.approx(15.0)


NEEDS = [DERIVED / f for f in ("aei_panel.parquet", "exposure_ff49.parquet",
                               "exposure_occupation.parquet", "benchmark_ff49.parquet")]


@pytest.mark.data
@pytest.mark.skipif(not RAW.exists() or not all(p.exists() for p in NEEDS),
                    reason="needs data/raw and the derived parquets")
def test_build_writes_every_table(tmp_path):
    paths = audit.build(out=tmp_path)
    assert {p.stem for p in paths} == {
        "releases", "metric_availability", "task_matching", "suppression", "r6_checks",
        "oews_coverage", "crosswalk_coverage", "exposure_coverage", "benchmark_coverage"}
    r6 = (tmp_path / "r6_checks.md").read_text()
    assert "| 2026-04 | 1p_api | 0.931 |" in r6
