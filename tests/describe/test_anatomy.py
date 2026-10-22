"""RQ1 descriptive anatomy: composition and concentration. Synthetic inputs only."""

from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.describe import anatomy

APR, MAY = date(2026, 4, 1), date(2026, 5, 1)


def _panel(rows, release="r6", source="claude_ai", taxonomy="soc_major"):
    """rows: (period_start, node_id, node_name, metric, value)."""
    n = len(rows)
    return pl.DataFrame({
        "release": [release] * n, "period_start": [r[0] for r in rows],
        "period_end": [r[0] for r in rows], "source": [source] * n,
        "geo_level": ["global"] * n, "geo_id": ["GLOBAL"] * n, "taxonomy": [taxonomy] * n,
        "level": [0] * n, "node_id": [r[1] for r in rows], "node_name": [r[2] for r in rows],
        "metric": [r[3] for r in rows],
        "value": [None if r[4] is None else float(r[4]) for r in rows], "definition": ["x"] * n,
    }, schema={c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                   else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS})


def test_gini_hand_cases():
    assert anatomy.gini(np.array([0, 0, 0, 1.0])) == pytest.approx(0.75)
    assert anatomy.gini(np.array([1, 1, 1, 1.0])) == pytest.approx(0.0)


def test_lorenz_endpoints():
    x, y = anatomy.lorenz_points(np.array([5.0, 1.0, 3.0, 1.0]))
    assert (x[0], y[0]) == (0.0, 0.0)
    assert (x[-1], y[-1]) == (pytest.approx(1.0), pytest.approx(1.0))
    assert len(x) == len(y) == 5 and np.all(np.diff(y) >= 0)


def test_top_shares():
    s = anatomy.concentration_stats(np.array([10.0, 40.0, 20.0, 30.0]))
    assert s["top10_share"] == pytest.approx(40.0)  # ceil(0.4) = 1 task
    assert s["top1_share"] == pytest.approx(40.0)
    assert s["top5_share"] == pytest.approx(40.0)
    assert s["n_tasks_50pct"] == 2
    assert s["n_tasks"] == 4


def _wages(emp, wage, status=None):
    n = len(emp)
    return pl.DataFrame({"soc6": [f"99-{i:04d}" for i in range(n)], "tot_emp": emp,
                         "a_median": wage,
                         "a_median_status": status or ["published"] * n})


def test_wage_deciles_equal_employment():
    w = _wages([100] * 10, [float(i) for i in range(1, 11)])
    out = anatomy.wage_deciles(w.select("soc6", "tot_emp"), w)
    assert out.sort("soc6")["decile"].to_list() == list(range(1, 11))


def test_topcoded_occupation_lands_in_top_decile():
    wage = [float(i) for i in range(1, 10)] + [239_200.0]
    status = ["published"] * 9 + ["topcoded"]
    w = _wages([100] * 10, wage[::-1], status[::-1])  # top-coded row listed first
    out = anatomy.wage_deciles(w.select("soc6", "tot_emp"), w)
    assert out.filter(pl.col("soc6") == "99-0000")["decile"].item() == 10


def test_suppressed_wage_is_excluded_from_deciles():
    w = _wages([100] * 4, [1.0, None, 3.0, 4.0], ["published", "suppressed", "published",
                                                 "published"])
    out = anatomy.wage_deciles(w.select("soc6", "tot_emp"), w)
    assert "99-0001" not in out["soc6"].to_list() and out.height == 3


def _occ_table():
    return pl.DataFrame({
        "release": ["r6"] * 2, "period_start": [APR] * 2, "source": ["claude_ai"] * 2,
        "basis": ["published"] * 2, "soc6": ["99-0000", "99-0001"], "usage_share": [60.0, 40.0],
        **{c: [10.0, 30.0] for c in anatomy.PATTERN_COLS},
    })


@pytest.mark.parametrize("kw,expected", [({}, "published"), ({"basis": "tasks"}, "tasks")])
def test_wage_decile_basis_passed_to_occupation_table(monkeypatch, kw, expected):
    seen = []

    def spy(panel, release, index, allocation="equal", basis="auto"):
        seen.append(basis)
        return _occ_table()

    monkeypatch.setattr(anatomy, "occupation_table", spy)
    w = _wages([100, 100], [1.0, 2.0])
    anatomy.by_wage_decile(pl.DataFrame(), None, w, w.select("soc6", "tot_emp"), None, **kw)
    assert seen == [expected]


def test_wage_decile_table_shape_and_null_row():
    w = _wages([100, 100, 100], [1.0, 2.0, None], ["published", "published", "suppressed"])
    nat = w.select("soc6", "tot_emp")
    occ = _occ_table().with_columns(soc6=pl.Series(["99-0000", "99-0002"]))
    import aideleg.describe.anatomy as a
    mp = pytest.MonkeyPatch()
    mp.setattr(a, "occupation_table", lambda *x, **k: occ)
    try:
        out = a.by_wage_decile(pl.DataFrame(), None, w, nat, None)
    finally:
        mp.undo()
    assert out.columns == ["decile", "emp_share", "usage_share", "n_occ", *a.PATTERN_COLS]
    last = out.row(out.height - 1, named=True)
    assert last["decile"] is None and last["usage_share"] == pytest.approx(40.0)
    assert last["directive_pct"] == pytest.approx(30.0) and last["n_occ"] == 1
    assert out["usage_share"].sum() == pytest.approx(100.0)
    assert out["emp_share"].sum() == pytest.approx(100.0)


def test_education_bins_left_closed():
    assert anatomy.education_bin(12.0) == "12–14"
    assert anatomy.education_bin(11.99) == "<12"
    assert anatomy.education_bin(18.0) == "≥18"
    assert anatomy.education_bin(14.0) == "14–16" and anatomy.education_bin(16.0) == "16–18"
    assert anatomy.education_bin(None) == "zero published usage"


def _collab(period, nid, name, taxonomy_rows):
    return [(period, nid, name, m, v) for m, v in taxonomy_rows]


def test_major_group_two_month_mean():
    pats = {c: 10.0 for c in anatomy.PATTERN_COLS}
    rows = []
    # group 11 published in both months, group 15 only in April (D13: not treated as 0)
    for per, nid, nm, pct, auto in [(APR, "11", "Mgmt", 40.0, 20.0),
                                    (MAY, "11", "Mgmt", 20.0, 40.0),
                                    (APR, "15", "Comp", 60.0, 80.0)]:
        rows += _collab(per, nid, nm, [("pct", pct), *{**pats, "automation_pct": auto}.items()])
    out = anatomy.by_major_group(_panel(rows))
    assert out.columns == ["major", "name", "usage_share", *anatomy.PATTERN_COLS]
    g11, g15 = (out.filter(pl.col("major") == m).row(0, named=True) for m in ("11", "15"))
    # weights: (40+20)/2 = 30 and (60+0)/2 = 30 -> 50 / 50
    assert g11["usage_share"] == pytest.approx(50.0) and g15["usage_share"] == pytest.approx(50.0)
    assert g11["automation_pct"] == pytest.approx((40 * 20 + 20 * 40) / 60)
    assert g15["automation_pct"] == pytest.approx(80.0)  # the unpublished May is skipped
    assert out["usage_share"].sum() == pytest.approx(100.0)


def test_education_by_task_not_published_row():
    rows = []
    for nid, pct, edu in [("1", 50.0, 11.0), ("2", 30.0, 12.0), ("3", 20.0, None)]:
        rows += [(APR, nid, f"t{nid}", "pct", pct), (APR, nid, f"t{nid}", "directive_pct", 5.0)]
        if edu is not None:
            rows.append((APR, nid, f"t{nid}", "human_education_years_mean", edu))
    rows += [(APR, "unmatched:none", "none", "pct", 99.0)]
    out = anatomy.by_education(_panel(rows, taxonomy="onet_task"))
    assert out.columns == ["bin", "usage_share", "n_tasks", *anatomy.PATTERN_COLS]
    by = {r["bin"]: r for r in out.iter_rows(named=True)}
    assert by["<12"]["usage_share"] == pytest.approx(50.0)
    assert by["12–14"]["usage_share"] == pytest.approx(30.0)
    assert by["zero published usage"]["usage_share"] == pytest.approx(20.0)
    assert by["zero published usage"]["n_tasks"] == 1
    assert out["bin"].to_list() == ["<12", "12–14", "zero published usage"]  # empty bins omitted


def test_concentration_rows_and_unmatched_excluded():
    def rel(release, source, vals, period=APR):
        rows = [(period, f"{i}", f"t{i}", "pct", v) for i, v in enumerate(vals)]
        rows.append((period, "unmatched:none", "none", "pct", 50.0))
        return _panel(rows, release=release, source=source, taxonomy="onet_task")
    panel = pl.concat([rel("r1", "claude_ai", [1, 1, 1, 1]), rel("r3", "1p_api", [3, 1]),
                       rel("r6", "claude_ai", [2, 2], APR), rel("r6", "claude_ai", [2, 2], MAY)])
    out = anatomy.concentration(panel)
    assert out.columns == ["release", "source", "n_tasks", "gini", "top1_share", "top5_share",
                           "top10_share", "n_tasks_50pct", "n_zero", "n_tasks_pos", "gini_pos",
                           "top1_share_pos", "top5_share_pos", "top10_share_pos"]
    assert sorted(out.select("release", "source").rows()) == [
        ("r1", "claude_ai"), ("r3", "1p_api"), ("r6", "claude_ai")]
    r3 = out.filter(pl.col("release") == "r3").row(0, named=True)
    assert r3["n_tasks"] == 2 and r3["top1_share"] == pytest.approx(75.0)
    assert r3["n_tasks_50pct"] == 1
    r1 = out.filter(pl.col("release") == "r1").row(0, named=True)
    assert r1["gini"] == pytest.approx(0.0) and r1["n_tasks_50pct"] == 2


def test_report_anatomy_writes_documents(tmp_path):
    from aideleg.results import rq1
    pats = {c: 20.0 for c in anatomy.PATTERN_COLS}
    rows = []
    for per in (APR, MAY):
        for nid, nm, pct in [("11", "Mgmt", 60.0), ("15", "Comp", 40.0)]:
            rows += [(per, nid, nm, m, v) for m, v in {"pct": pct, **pats}.items()]
    soc = _panel(rows)
    det = [(per, f"{c}.00", c, m, v) for per in (APR, MAY) for c in ("11-1011", "15-1252")
           for m, v in {"pct": 50.0, **pats}.items()]
    det = _panel(det, taxonomy="soc_detailed")
    task = _panel([(APR, str(i), f"t{i}", m, v) for i in range(3)
                   for m, v in {"pct": 10.0 + i, "human_education_years_mean": 13.0 + i,
                                **pats}.items()], taxonomy="onet_task")
    nat = pl.DataFrame({"soc6": ["11-1011", "15-1252"], "tot_emp": [100, 200]})
    wages = nat.with_columns(a_median=pl.Series([50_000.0, 90_000.0]))
    out, figs = tmp_path / "o", tmp_path / "f"
    paths = rq1.report_anatomy(out, fig_dir=figs, panel=pl.concat([soc, det, task]), index=None,
                               wages=wages, national=nat, soc_structure=None)
    names = {p.name for p in paths}
    assert {"anatomy.md", "fig_rq1_lorenz.png", "fig_rq1_composition_major.pdf"} <= names
    md = (out / "anatomy.md").read_text(encoding="utf-8")
    assert md.startswith("Generated by `aideleg.results.rq1`.")
    assert "published cells only" in md and "no p-value" in md and "(D9)" in md
    assert "suppression regimes (PAP §5)" in md
    # AEI's definition: education the task requires, never a claim about the person
    assert "mean estimated years of human education required for the task" in md
    assert "person in the conversation" not in md


def test_concentration_positive_only_and_harmonised():
    rows = [(APR, str(i), f"t{i}", "pct", v) for i, v in enumerate([60.0, 30.0, 10.0, 0.0, 0.0])]
    rows += [(APR, "9", "t9", "pct", 0.004)]  # rounds to 0.00 in the harmonised series
    panel = _panel(rows, release="r3", source="1p_api", taxonomy="onet_task")
    r = anatomy.concentration(panel).row(0, named=True)
    assert r["n_tasks"] == 6 and r["n_zero"] == 2 and r["n_tasks_pos"] == 4
    assert r["gini_pos"] < r["gini"]  # zero-usage tasks raise the as-published Gini
    assert r["top1_share_pos"] == pytest.approx(60.0 / 100.004 * 100)
    # n_tasks_pos is the same set the Gini is computed on
    pos = np.array([60.0, 30.0, 10.0, 0.004])
    assert r["gini_pos"] == pytest.approx(anatomy.gini(pos / pos.sum() * 100))
    h = anatomy.concentration_harmonised(panel).row(0, named=True)
    assert h["n_tasks"] == 3 and h["top1_share"] == pytest.approx(60.0)
    assert h["gini"] == pytest.approx(anatomy.gini(np.array([60.0, 30.0, 10.0])))


def test_decile_pattern_cell_unpublished_is_excluded_not_zeroed(monkeypatch):
    occ = pl.DataFrame({
        "release": ["r6"] * 2, "period_start": [APR] * 2, "source": ["claude_ai"] * 2,
        "basis": ["published"] * 2, "soc6": ["99-0000", "99-0001"], "usage_share": [50.0, 50.0],
        **{c: [10.0, 10.0] for c in anatomy.PATTERN_COLS}})
    occ = occ.with_columns(directive_pct=pl.Series([None, 20.0]))
    monkeypatch.setattr(anatomy, "occupation_table", lambda *a, **k: occ)
    wages = _wages([1, 1, 1000], [1.0, 2.0, 3.0])  # the first two share decile 1
    out = anatomy.by_wage_decile(pl.DataFrame(), None, wages, wages.select("soc6", "tot_emp"),
                                 None)
    d1 = out.filter(pl.col("decile") == 1).row(0, named=True)
    assert d1["n_occ"] == 2 and d1["usage_share"] == pytest.approx(100.0)
    assert d1["directive_pct"] == pytest.approx(20.0)  # not (0 + 20) / 2
    assert d1["learning_pct"] == pytest.approx(10.0)
