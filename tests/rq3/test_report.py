"""RQ3 summary and the checks every rq3 and h6 doc must pass (PAP §7 D11, D3; spec §6).

Synthetic docs except the `data` tests, which read the committed docs under docs/results/.
"""

import ast
from pathlib import Path

import polars as pl
import pytest

from aideleg.config import ROOT
from aideleg.results.common import FORBIDDEN_PHRASES, WORDING
from aideleg.rq3 import report

RQ3 = ROOT / "docs/results/rq3"
H6 = ROOT / "docs/results/h6"

_W1 = (
    "  - Fixed wording: H5 is not rejected (H0: b = bbar). Interval [-2.76, 6.68] pp per 1 SD; "
    "the test had 80% power only against a departure from H0 of at least 7.43 pp per 1 SD "
    "(MDE at Holm level 0.025)."
)
_W2 = (
    "  - Fixed wording: H5b is not rejected (H0: b = bbar). Interval [-1.86, 8.79] pp per 1 SD; "
    "the test had 80% power only against a departure from H0 of at least 8.38 pp per 1 SD "
    "(MDE at Holm level 0.025)."
)
_RECORD = "\n".join(
    [
        "# Confirmatory test of H5 and H5b",
        "",
        "| specification | b |",
        "|---|---|",
        "| H5 | 1.958 |",
        "",
        "- **H5.** Holm level reached: None; primary rejection: False; "
        "R13 co-condition met: False.",
        "  - Interval b +- c_0.05 x s: [-2.764, 6.681] pp.",
        _W1,
        "- **H5b.** Holm level reached: None; primary rejection: False; "
        "R13 co-condition met: False.",
        _W2,
        "",
    ]
)


def _synthetic_docs(tmp_path: Path) -> tuple[Path, Path]:
    out = tmp_path / "rq3"
    out.mkdir()
    for name, title in [
        ("influence.md", "Influence diagnostics — not part of the decision"),
        ("event_study.md", "Event studies (exploratory)"),
        ("terciles.md", "Tercile portfolios (exploratory)"),
    ]:
        (out / name).write_text(
            f"# {title}\n\n| x | 1.234 |\n|---|---|\n\n{WORDING}\n", encoding="utf-8"
        )
    record = tmp_path / "confirmatory_h5.md"
    record.write_text(_RECORD, encoding="utf-8")
    return out, record


def test_fixed_wording_verbatim():
    assert report.fixed_wording(_RECORD) == [_W1, _W2]


def test_summary_reports_no_exploratory_estimates(tmp_path):
    out, record = _synthetic_docs(tmp_path)
    path = report.write_summary(out, record=record, commit="0" * 40)
    text = path.read_text(encoding="utf-8")
    assert path == out / "summary.md"
    assert text.startswith("# RQ3: what the market evidence can and cannot yet say\n")
    assert not [ln for ln in text.splitlines() if ln.startswith("|")]
    for line in report.fixed_wording(_RECORD):
        assert line in text.splitlines()
    assert "0" * 40 in text and "influence.md" in text
    assert "(event_study.md)" in text and "(terciles.md)" in text
    assert "1.234" not in text
    assert text.count(WORDING) == 1 and text.rstrip("\n").endswith(WORDING)


def test_summary_refuses_record_without_wording(tmp_path):
    out, record = _synthetic_docs(tmp_path)
    record.write_text("# Confirmatory test of H5 and H5b\n", encoding="utf-8")
    with pytest.raises(ValueError):
        report.write_summary(out, record=record, commit="0" * 40)


def test_md_table_formats_floats_and_nulls():
    df = pl.DataFrame({"a": ["x", "y"], "b": [1.23456, None], "n": [3, 4]})
    assert report.md_table(df, floats=2).splitlines() == [
        "| a | b | n |",
        "|---|---|---|",
        "| x | 1.23 | 3 |",
        "| y | — | 4 |",
    ]


def _h6_docs() -> list[Path]:
    # docs/results/h6 is written by Tasks 9-13; until then the glob is empty and only rq3 is
    # checked.
    return sorted(H6.glob("*.md"))


@pytest.mark.data
def test_every_exploratory_doc_is_labelled():
    docs = [
        RQ3 / n
        for n in ("event_study.md", "eisfeldt_replication.md", "terciles.md", "fama_macbeth.md")
    ] + _h6_docs()
    for p in docs:
        text = p.read_text(encoding="utf-8")
        assert "exploratory" in text.splitlines()[0], p.name
        assert text.rstrip("\n").endswith(WORDING), p.name


@pytest.mark.data
def test_rq3_h6_docs_wording():
    docs = sorted(RQ3.glob("*.md")) + _h6_docs()
    assert docs
    for p in docs:
        text = p.read_text(encoding="utf-8")
        assert text.count(WORDING) == 1, p.name
        low = text.replace(WORDING, "").lower()
        assert not [f for f in FORBIDDEN_PHRASES if f in low], p.name


@pytest.mark.data
def test_rq3_docs_state_zero_assigned_share():
    reported = {
        RQ3 / "influence.md": ["B"],
        RQ3 / "event_study.md": ["A_r2", "A_pooled"],
        RQ3 / "eisfeldt_replication.md": ["A_r2", "A_pooled"],
        RQ3 / "terciles.md": ["B", "A_r2", "A_pooled"],
        RQ3 / "fama_macbeth.md": ["B", "A_r2", "A_pooled"],
    }
    # h6/gap.md is written by Plan 3 Task 12 (it uses Design B's z_usage); checked once it exists.
    if (H6 / "gap.md").exists():
        reported[H6 / "gap.md"] = ["B"]
    # the designs in each CSV must be among those the doc is checked for
    for md in ("event_study", "terciles", "fama_macbeth"):
        csv_designs = set(pl.read_csv(RQ3 / f"{md}.csv")["design"].drop_nulls().to_list())
        assert csv_designs <= set(reported[RQ3 / f"{md}.md"]), md
    for p, designs in reported.items():
        text = p.read_text(encoding="utf-8")
        for line in report.zero_assigned_lines(designs):
            assert line in text, (p.name, line)


def _figure_names(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    consts = {
        t.id: n.value.value
        for n in tree.body
        if isinstance(n, ast.Assign)
        and isinstance(n.value, ast.Constant)
        and isinstance(n.value.value, str)
        for t in n.targets
        if isinstance(t, ast.Name)
    }
    names = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and getattr(node.func, "id", getattr(node.func, "attr", None)) == "save_figure"
        ):
            continue
        arg = (
            node.args[1]
            if len(node.args) > 1
            else next(k.value for k in node.keywords if k.arg == "name")
        )
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            names.append(arg.value)
        elif isinstance(arg, ast.Name) and arg.id in consts:
            names.append(consts[arg.id])
        else:
            raise AssertionError(f"{path.name}: figure name is not a string literal or constant")
    return names


def test_figure_names_prefixed():
    files = sorted((ROOT / "src/aideleg/rq3").glob("*.py")) + sorted(
        (ROOT / "src/aideleg/h6").glob("*.py")
    )
    names = [n for f in files for n in _figure_names(f)]
    assert names  # events and terciles each save one
    assert [n for n in names if not n.startswith(("fig_rq3_", "fig_h6_"))] == []
