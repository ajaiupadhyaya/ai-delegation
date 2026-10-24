"""The robustness appendix (Plan 4 Task 15): coverage gate, summary, implementation choices and
the two forest figures. PAP §8.1: no row is summarised by counting significant ones."""

import re

import matplotlib.text
import polars as pl
import pytest

from aideleg.config import ROOT
from aideleg.robustness import appendix, figures, registry, report, upstream

ROB = ROOT / registry.OUT_DIR
COUNT_PATTERNS = (
    r"\b\d+\s+(of|out of)\b",
    r"\b(most|majority|all but|none of the)\b.*\bvariants?\b",
    r"\bsignificant in\b",
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_root(tmp_path):
    """Every row reported once: Plan 4 files for the Plan 4 rows, the H5 record for R12/R13."""
    for row in registry.ROWS.values():
        for out in row.outputs:
            p = tmp_path / out
            if not p.exists():
                _write(p, "# Confirmatory test\n\nR12 ranks; R13 drop Softw\n")
    _write(tmp_path / "docs/results/rq3/terciles.md", "# Terciles\n\nnothing\n")
    return tmp_path


# --- coverage gate ----------------------------------------------------------------------------


def test_every_row_covered_exactly_once():
    found = appendix.coverage()
    assert sorted(found) == sorted(registry.ROWS)
    bad = {rid: files for rid, files in found.items() if len(files) != 1}
    assert not bad, f"rows not reported exactly once: {bad}"


def test_coverage_fails_on_a_row_reported_twice(tmp_path):
    root = _fixture_root(tmp_path)
    assert all(len(v) == 1 for v in appendix.coverage(root).values())
    _write(
        root / "docs/results/rq3/extra.md", "# R5: robustness row, equal-weighted returns\n\nx\n"
    )
    assert len(appendix.coverage(root)["R5"]) == 2
    _write(root / "docs/results/rq2/bounds.md", "# RQ2: widths of the R7 bounds\n")
    assert len(appendix.coverage(root)["R7"]) == 1
    _write(root / "docs/results/h6/extra.csv", "row,R07,estimate\n1,2,3\n")
    assert len(appendix.coverage(root)["R7"]) == 2


def test_coverage_fails_on_a_row_with_no_report(tmp_path):
    root = _fixture_root(tmp_path)
    (root / "docs/results/robustness/R17.md").unlink()
    assert appendix.coverage(root)["R17"] == []
    _write(root / registry.H5_RECORD, "# Confirmatory test\n\nR12 only\n")
    assert appendix.coverage(root)["R13"] == []


# --- summary ----------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def summary_text():
    return (ROB / "summary.md").read_text(encoding="utf-8")


def test_summary_has_no_counts(summary_text):
    for pat in COUNT_PATTERNS:
        hits = [ln for ln in summary_text.splitlines() if re.search(pat, ln, flags=re.I)]
        assert not hits, (pat, hits[:3])


def test_summary_lists_every_row(summary_text):
    lines = [ln for ln in summary_text.splitlines() if ln.startswith("| ")]
    for rid, row in registry.ROWS.items():
        mine = [ln for ln in lines if ln.split("|")[1].strip() == rid]
        assert mine, rid
        if row.owner == "plan4":
            df = pl.read_csv(ROOT / row.outputs[0], infer_schema_length=0)
            labels = set(df["label"].to_list())
        else:
            labels = {appendix.SCRIPT_LABELS[rid]}
        for lab in labels:
            assert any(f"| {lab} |" in ln for ln in mine), (rid, lab)


def test_summary_is_one_table_with_sources_and_links(summary_text):
    heads = [ln for ln in summary_text.splitlines() if ln.startswith("| row |")]
    assert heads == ["| " + " | ".join(appendix.SUMMARY_COLUMNS) + " |"]
    src = appendix.pap_sources()
    assert sorted(src) == sorted(registry.ROWS)
    assert src["R1"] == "spec §5.6; P16" and src["R20"] == "Task 10 ruling"
    for rid in registry.ROWS:
        stem = registry.output_stem(rid)
        link = (
            "[confirmatory_h5.md](../confirmatory_h5.md)"
            if rid in ("R12", "R13")
            else (f"[{stem}.md]({stem}.md)")
        )
        assert any(
            ln.split("|")[1].strip() == rid and f"| {src[rid]} |" in ln and link in ln
            for ln in summary_text.splitlines()
            if ln.startswith("| ")
        ), rid


def test_summary_states_interval_and_wording_rules(summary_text):
    assert appendix.INTERVAL_STATEMENT in summary_text
    assert appendix.P14_STATEMENT in summary_text
    assert summary_text.rstrip("\n").endswith(upstream.WORDING)


def test_primary_matches_where_the_variant_is_the_primary():
    """R15 is identical to the primary by construction (C-70); R25's and R38's point estimates
    are the primary RQ1 ones; R18/R19/R34/R35 vary only the inference of the primary slope."""
    recs = appendix.load_records()
    for rid in ("R15", "R25", "R38", "R18", "R19", "R34", "R35"):
        sub = recs.filter(pl.col("row_id") == rid, pl.col("estimate").is_not_null())
        matched = 0
        for r in sub.iter_rows(named=True):
            prim = appendix.primary_for(r)
            if prim is None:
                continue
            matched += 1
            if prim.quoted:  # quoted at confirmatory_h5.md's printed precision
                assert prim.text == f"{r['estimate']:.3f}", (rid, r["estimand"])
            else:
                assert prim.est == pytest.approx(r["estimate"], abs=1e-9), (rid, r["estimand"])
        assert matched, rid


def test_primary_mapping_by_kind():
    recs = appendix.load_records()

    def first(rid, part, estimand):
        r = recs.filter(
            pl.col("row_id") == rid, pl.col("part") == part, pl.col("estimand") == estimand
        ).row(0, named=True)
        return appendix.primary_for(r)

    assert first("R1", "market", recs.filter(pl.col("row_id") == "R1")["estimand"][0]).text == (
        "1.958"
    )
    assert first("R27", "coe", "coe").est == pytest.approx(-0.1763412001559772)
    assert first("R31", "covariates", "log_wage") is None  # not a coefficient of H3
    assert first("R22", "unbalanced", "beta (pp per year)").est == pytest.approx(4.979177595216438)
    assert first("R17", "rq2", "spearman z_eloundou vs z_usage").est == pytest.approx(0.7682653061)
    pooled = first("R4", "rq2", "spearman z_eloundou vs z_usage")
    a_pooled = pl.read_csv(ROOT / "docs/results/rq2/could_vs_does.csv").filter(
        pl.col("design") == "A_pooled",
        pl.col("aei") == "z_usage",
        pl.col("benchmark") == "z_eloundou",
    )["spearman"][0]
    assert pooled.est == pytest.approx(a_pooled)
    r23 = recs.filter(pl.col("row_id") == "R23", pl.col("estimate").is_not_null())
    assert all(appendix.primary_for(r) is None for r in r23.iter_rows(named=True))
    r9 = recs.filter(pl.col("row_id") == "R9")
    assert all(appendix.primary_for(r) is None for r in r9.iter_rows(named=True))


def test_market_intervals_are_the_c005_interval():
    recs = appendix.load_records().filter(pl.col("unit") == report.MARKET_UNIT)
    assert recs.height
    for r in recs.iter_rows(named=True):
        half = r["crit_005"] * r["scale"]
        assert r["ci_lo"] == pytest.approx(r["estimate"] - half, abs=1e-9), r["row_id"]
        assert r["ci_hi"] == pytest.approx(r["estimate"] + half, abs=1e-9), r["row_id"]


# --- implementation choices -------------------------------------------------------------------


def test_implementation_choices_lists_every_default():
    text = (ROB / "implementation_choices.md").read_text(encoding="utf-8")
    notes = appendix.default_notes()
    assert notes
    titles = {(e["kind"], e["n"]): e["title"] for e in appendix.paplog.entries()}
    for rid, note in notes:
        assert note in text, (rid, note[:60])
        cs = re.findall(r"\bC-(\d+)\b", note)
        assert cs, note
        for c in cs:
            assert f"C-{c} ({titles[('C', int(c))]})" in text
    assert "D-2" in text and appendix.INTERVAL_STATEMENT in text
    assert f"C-80 ({titles[('C', 80)]})" in text
    assert appendix.P14_STATEMENT in text


# --- docs wording -----------------------------------------------------------------------------


def test_robustness_docs_wording():
    docs = sorted(ROB.glob("*.md"))
    assert {"summary.md", "implementation_choices.md"} <= {p.name for p in docs}
    for p in docs:
        text = p.read_text(encoding="utf-8")
        assert text.rstrip("\n").endswith(upstream.WORDING), p.name
        assert text.count(upstream.WORDING) == 1, p.name
        low = text.replace(upstream.WORDING, "").lower()
        assert not [f for f in upstream.FORBIDDEN_PHRASES if f in low], p.name


# --- figures ----------------------------------------------------------------------------------


def _fixture_records():
    def rec(rid, part, applies, est, lo, hi):
        return {
            **{c: None for c in report.ROBUSTNESS_COLUMNS},
            "row_id": rid,
            "part": part,
            "applies_to": applies,
            "label": "robustness",
            "unit": report.MARKET_UNIT,
            "estimate": est,
            "ci_lo": lo,
            "ci_hi": hi,
        }

    return pl.DataFrame(
        [
            rec("R5", "market", "H5", 1.0, -2.0, 4.0),
            rec("R5", "market", "H5b", 2.0, -1.0, 5.0),
            rec("R7", "market", "H5", 9.0, 3.5, 14.5),
        ],
        infer_schema_length=None,
    )


def test_forest_no_stars():
    fig = figures.forest(
        _fixture_records(), {"H5": (1.5, -3.0, 6.0), "H5b": (3.0, -2.0, 8.0)}, "Market rows"
    )
    texts = [t.get_text() for t in fig.findobj(matplotlib.text.Text)]
    assert any("R05 market" in t for t in texts)
    assert not [t for t in texts if "*" in t]
    assert not [t for t in texts if re.search(r"\b\d+\s+(of|out of)\b", t)]


def test_forest_one_point_per_row_and_part():
    fig = figures.forest(_fixture_records(), {"H5": (1.5, -3.0, 6.0)}, "x")
    (ax,) = fig.axes
    labels = [t.get_text() for t in ax.get_yticklabels()]
    assert labels == ["R05 market", "R07 market"]


def test_robustness_figure_names(tmp_path):
    written = figures.write_figures(out_dir=tmp_path)
    assert {p.stem for p in written} == {"fig_robustness_market", "fig_robustness_rq1"}
    assert {p.suffix for p in written} == {".pdf", ".png"}
    on_disk = {p.stem for p in (ROOT / "docs/paper/figures").glob("fig_robustness_*")}
    assert on_disk == {"fig_robustness_market", "fig_robustness_rq1"}
