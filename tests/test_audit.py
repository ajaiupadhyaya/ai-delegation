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


# Allowlist (controller ruling, Task 13 review): every correlation or regression in
# audit.py sits in one of these functions; `rank_correlations` (the descriptive
# could-vs-does Spearman) is called only from `build`. Checked on the AST, so a generic
# loop over metrics cannot bypass it by building names or method strings.
STAT_NAMES = {"corr", "cov", "corrcoef", "pearsonr", "spearmanr", "kendalltau", "pearson",
              "spearman", "kendall", "ols", "wls", "glm", "lstsq", "polyfit", "linregress",
              "regress", "regression", "fit"}
STAT_ALLOWED = {"bounds_ff49", "r6_allocated_vs_published"}
RANKCORR_ALLOWED = {"build"}
BANNED_MODULES = ("statsmodels", "scipy", "sklearn", "numpy", "linearmodels")


def _stat_violations(source: str) -> list[str]:
    """Statistical names, method strings or modules outside the allowlist."""
    tree = ast.parse(source)
    out: list[str] = []
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                  and isinstance(n.body[0], ast.Expr)
                  and isinstance(n.body[0].value, ast.Constant)}

    def visit(node: ast.AST, func: str | None) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func = node.name if func is None else func  # nested defs inherit the outer
        name = None
        if isinstance(node, ast.Attribute):
            name = node.attr
        elif isinstance(node, ast.Name):
            name = node.id
        elif isinstance(node, ast.alias):
            name = node.asname or node.name
            if any(node.name.split(".")[0] == m for m in BANNED_MODULES):
                out.append(f"import {node.name}")
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] in BANNED_MODULES:
                out.append(f"from {node.module}")
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in docstrings
              and node.value.lower() in STAT_NAMES and func not in STAT_ALLOWED):
            out.append(f"string {node.value!r} in {func}")
        if name is not None:
            low = name.lower()
            if low in STAT_NAMES and func not in STAT_ALLOWED:
                out.append(f"{name} in {func}")
            if low == "rank_correlations" and func not in RANKCORR_ALLOWED:
                out.append(f"{name} in {func}")
        for child in ast.iter_child_nodes(node):
            visit(child, func)

    visit(tree, None)
    return out


def test_correlations_only_in_allowlisted_functions():
    assert _stat_violations(SOURCE) == []


@pytest.mark.parametrize("snippet", [
    "def f(df, ms):\n    return [df.select(pl.corr(m, 'wage')) for m in ms]",
    "def f(df):\n    return getattr(pl, 'corr')('a', 'b')",
    "def f(df):\n    return df.select(pl.corr('a', 'b', method=M))",
    "import statsmodels.api as sm",
    "def build():\n    pass\ndef g(b, e):\n    return rank_correlations(b, e)",
])
def test_allowlist_catches_bypasses(snippet):
    assert _stat_violations(snippet)


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
