"""Exposure indices on a 3-occupation, 2-industry toy.

AEI data are conversations matched to O*NET tasks; the toy says nothing about jobs.
"""

from datetime import date

import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex
from aideleg.exposure import (
    aggregate_to_ff49,
    build_exposure,
    build_occupation_exposure,
    industry_exposure,
    occupation_exposure,
)

SOCS = ["15-1252", "13-2011", "25-1021"]


def _occ(usage=(50.0, 30.0, 20.0), auto=(40.0, 40.0, 40.0), aug=(60.0, 60.0, 60.0),
         lb=None, ub=None):
    n = len(usage)
    return pl.DataFrame({
        "soc6": SOCS[:n], "usage_share": list(usage),
        "automation_pct": list(auto), "augmentation_pct": list(aug),
        "automation_share_all_lb": list(lb) if lb else [None] * n,
        "automation_share_all_ub": list(ub) if ub else [None] * n,
    }, schema_overrides={"automation_share_all_lb": pl.Float64,
                         "automation_share_all_ub": pl.Float64})


# employment shares 25, 25, 50 (percent of national detailed-occupation employment)
NATIONAL = pl.DataFrame({"soc6": SOCS, "title": ["a", "b", "c"],
                         "tot_emp": [100, 100, 200], "a_median": [1.0, 1.0, 1.0]})
# industry 511200 (FF49 32): weights 0.5, 0.5, 0; industry 522100 (FF49 45): 0, 0.25, 0.75
MATRIX = pl.DataFrame({
    "naics": ["511200", "511200", "522100", "522100"],
    "naics_title": ["Software", "Software", "Banks", "Banks"],
    "soc6": ["15-1252", "13-2011", "13-2011", "25-1021"],
    "tot_emp": [50, 50, 50, 150],
}).with_columns(emp_share_in_industry=pl.col("tot_emp") / pl.col("tot_emp").sum().over("naics"))
CROSSWALK = pl.DataFrame({"naics": ["5112", "5221"], "ff49": [32, 45], "weight": [1.0, 1.0]})
NAMES = pl.DataFrame({"ff49": [32, 45], "ff49_short": ["BusSv", "Banks"]})


def _by(df, soc):
    return df.filter(pl.col("soc6") == soc).row(0, named=True)


def test_usage_intensity_hand_computed():
    out = occupation_exposure(_occ(), NATIONAL)
    assert [_by(out, s)["U"] for s in SOCS] == pytest.approx([2.0, 1.2, 0.4])


def test_delegation_uses_automation_share():
    out = occupation_exposure(_occ(), NATIONAL)
    for s in SOCS:
        r = _by(out, s)
        assert r["D"] == pytest.approx(0.4 * r["U"])
        assert r["A"] == pytest.approx(0.6 * r["U"])


def test_delegation_bounds_use_share_of_all():
    out = occupation_exposure(_occ(lb=(30, 30, 30), ub=(50, 50, 50)), NATIONAL)
    r = _by(out, "15-1252")
    assert (r["D_lb"], r["D_ub"]) == pytest.approx((0.6, 1.0))


def test_industry_is_employment_weighted():
    ind = industry_exposure(occupation_exposure(_occ(), NATIONAL), MATRIX, CROSSWALK,
                            names=NAMES)
    r = ind.filter(pl.col("ff49") == 32).row(0, named=True)
    assert r["E_usage"] == pytest.approx(1.6)
    assert r["ff49_short"] == "BusSv"
    assert ind.filter(pl.col("ff49") == 45)["E_usage"][0] == pytest.approx(0.25 * 1.2 + 0.75 * 0.4)


def test_z_scores_have_unit_sd():
    ind = industry_exposure(occupation_exposure(_occ(), NATIONAL), MATRIX, CROSSWALK,
                            names=NAMES)
    for c in ("z_usage", "z_delegation", "z_augmentation"):
        assert ind[c].mean() == pytest.approx(0.0, abs=1e-12)
        assert ind[c].std(ddof=0) == pytest.approx(1.0)


def test_unmatched_zero_or_drop():
    occ = _occ(usage=(60.0, 40.0), auto=(40.0, 40.0), aug=(60.0, 60.0))  # 25-1021 has no AEI usage
    zero = occupation_exposure(occ, NATIONAL)
    assert (_by(zero, "25-1021")["U"], _by(zero, "25-1021")["D"]) == (0.0, 0.0)
    assert not _by(zero, "25-1021")["has_usage"]
    drop = occupation_exposure(occ, NATIONAL, unmatched="drop")
    assert "25-1021" not in drop["soc6"].to_list()
    ind = industry_exposure(drop, MATRIX, CROSSWALK, names=NAMES)
    banks = ind.filter(pl.col("ff49") == 45).row(0, named=True)
    assert banks["E_usage"] == pytest.approx(_by(drop, "13-2011")["U"])  # renormalised
    assert banks["emp_covered_share"] == pytest.approx(0.25)


def test_null_pattern_share_is_excluded_and_counted():
    occ = _occ(auto=(40.0, None, 40.0), aug=(60.0, None, 60.0))
    exp = occupation_exposure(occ, NATIONAL)
    assert _by(exp, "13-2011")["U"] == pytest.approx(1.2)
    assert _by(exp, "13-2011")["D"] is None
    ind = industry_exposure(exp, MATRIX, CROSSWALK, names=NAMES)
    sw = ind.filter(pl.col("ff49") == 32).row(0, named=True)
    assert sw["E_delegation"] == pytest.approx(0.4 * 2.0)  # 13-2011 dropped, weight renormalised
    assert sw["E_usage"] == pytest.approx(1.6)
    assert sw["emp_covered_share"] == pytest.approx(0.5)


def test_usage_summed_by_oews_code_before_ratio():
    # 15-1252 and 15-1253 both roll up to the OEWS aggregate 15-1250
    nat = pl.DataFrame({"soc6": ["15-1250", "25-1021"], "title": ["x", "y"],
                        "tot_emp": [100, 100], "a_median": [1.0, 1.0]})
    occ = pl.DataFrame({"soc6": ["15-1252", "15-1253", "25-1021"],
                        "usage_share": [30.0, 30.0, 40.0],
                        "automation_pct": [20.0, 60.0, 50.0],
                        "augmentation_pct": [80.0, 40.0, 50.0]})
    out = occupation_exposure(occ, nat)
    r = _by(out, "15-1250")
    assert r["U"] == pytest.approx(1.2)
    assert r["automation_pct"] == pytest.approx(40.0)  # usage-weighted mean
    assert r["D"] == pytest.approx(0.48)


def test_aggregate_to_ff49_crosswalk_split():
    occ_values = pl.DataFrame({"soc6": SOCS, "x": [1.0, 2.0, 3.0]})
    xw = pl.DataFrame({"naics": ["5112", "5112", "5221"], "ff49": [32, None, 45],
                       "weight": [0.5, 0.5, 1.0]}, schema_overrides={"ff49": pl.Int64})
    out = aggregate_to_ff49(occ_values, ["x"], MATRIX, xw)
    assert out.filter(pl.col("ff49") == 32)["x"][0] == pytest.approx(1.5)
    assert out.filter(pl.col("ff49") == 45)["x"][0] == pytest.approx(0.25 * 2 + 0.75 * 3)
    assert out.filter(pl.col("ff49") == 32)["emp"][0] == pytest.approx(50.0)
    assert out["ff49"].null_count() == 0


# --- designs --------------------------------------------------------------------------

INDEX = TaskIndex(
    {"write code": [1], "plan budgets": [2], "teach": [3]},
    {1: ["15-1252.00"], 2: ["13-2011.00"], 3: ["25-1021.00"]},
)
TASKS = [("1", "write code"), ("2", "plan budgets"), ("3", "teach")]


def _panel(release, start, taxonomy, rows):
    """rows: (node_id, node_name, metric, value)."""
    n = len(rows)
    return pl.DataFrame({
        "release": [release] * n, "period_start": [start] * n, "period_end": [start] * n,
        "source": ["claude_ai"] * n, "geo_level": ["global"] * n, "geo_id": ["GLOBAL"] * n,
        "taxonomy": [taxonomy] * n, "level": [0] * n,
        "node_id": [r[0] for r in rows], "node_name": [r[1] for r in rows],
        "metric": [r[2] for r in rows], "value": [float(r[3]) for r in rows],
        "definition": ["x"] * n,
    }, schema={c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                   else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS})


def _task_rows(pcts, autos, filtered=10.0):
    rows = []
    for (nid, name), p, a in zip(TASKS, pcts, autos, strict=True):
        rows += [(nid, name, "pct", p), (nid, name, "automation_pct", a),
                 (nid, name, "augmentation_pct", 100 - a), (nid, name, "filtered_pct", filtered)]
    return rows


def _soc_rows(pcts, autos):
    rows = []
    for soc, p, a in zip(SOCS, pcts, autos, strict=True):
        code = soc + ".00"
        rows += [(code, soc, "pct", p), (code, soc, "automation_pct", a),
                 (code, soc, "augmentation_pct", 100 - a), (code, soc, "none_pct", 5.0)]
    return rows


def _design_panel(r6_scale=1.0):
    r2 = _panel("r2", date(2025, 2, 24), "onet_task", _task_rows([50, 30, 20], [40, 20, 60]))
    r6a = _panel("r6", date(2026, 4, 1), "soc_detailed",
                 _soc_rows([20 * r6_scale, 30, 50], [10 * r6_scale, 30, 50]))
    r6b = _panel("r6", date(2026, 5, 1), "soc_detailed",
                 _soc_rows([30, 30 * r6_scale, 40], [20, 40 * r6_scale, 60]))
    return pl.concat([r2, r6a, r6b])


OCC_KW = dict(index=INDEX, national=NATIONAL, soc_structure=None)
KW = dict(OCC_KW, matrix=MATRIX, crosswalk=CROSSWALK, names=NAMES)


def test_design_b_reads_only_r2():
    base = build_exposure("B", panel=_design_panel(), **KW)
    moved = build_exposure("B", panel=_design_panel(r6_scale=1.7), **KW)
    assert base.equals(moved)
    assert set(base["design"]) == {"B"}
    assert not base["exploratory"].any()
    occ = build_occupation_exposure("B", panel=_design_panel(), **OCC_KW)
    assert _by(occ, "15-1252")["U"] == pytest.approx(2.0)


def test_a_r2_equals_b_but_labelled_exploratory():
    b = build_exposure("B", panel=_design_panel(), **KW)
    a = build_exposure("A_r2", panel=_design_panel(), **KW)
    assert a.drop("design", "exploratory").equals(b.drop("design", "exploratory"))
    assert set(a["design"]) == {"A_r2"} and a["exploratory"].all()


def test_a_pooled_equal_release_weights():
    occ = build_occupation_exposure("A_pooled", panel=_design_panel(), **OCC_KW)
    # 15-1252: r2 usage 50, r6 months 20 and 30 -> r6 25 -> pooled 37.5; emp share 25%
    r = _by(occ, "15-1252")
    assert r["usage_share"] == pytest.approx(37.5)
    assert r["U"] == pytest.approx(1.5)
    # automation: r2 40, r6 mean(10, 20) = 15 -> 27.5
    assert r["automation_pct"] == pytest.approx(27.5)
    assert r["D_lb"] is None and r["D_ub"] is None  # bounds are not definition-stable
    moved = build_exposure("A_pooled", panel=_design_panel(r6_scale=1.7), **KW)
    assert not moved.equals(build_exposure("A_pooled", panel=_design_panel(), **KW))
    assert build_exposure("A_pooled", panel=_design_panel(), **KW)["exploratory"].all()


def test_unknown_design_raises():
    with pytest.raises(ValueError):
        build_exposure("C", panel=_design_panel(), **KW)
