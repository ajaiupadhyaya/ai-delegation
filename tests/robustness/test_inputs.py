"""New constructions for the exposure variants (Plan 4 Task 6): R2, R11, R14, R27, R29, R32, R33."""

from datetime import date
from pathlib import Path

import openpyxl
import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex
from aideleg.robustness.inputs import (
    bls_soc_crosswalk,
    emp_weighted_naics_ff49,
    employment_allocation_table,
    index_29_2,
    wage_bill_coverage,
    wage_bill_matrix,
)

P0, P1 = date(2025, 1, 6), date(2025, 1, 13)


def _panel(rows, release="r2", source="claude_ai"):
    """rows: (node_id, node_name, metric, value), global onet_task rows."""
    n = len(rows)
    return pl.DataFrame(
        {
            "release": [release] * n,
            "period_start": [P0] * n,
            "period_end": [P1] * n,
            "source": [source] * n,
            "geo_level": ["global"] * n,
            "geo_id": ["GLOBAL"] * n,
            "taxonomy": ["onet_task"] * n,
            "level": [0] * n,
            "node_id": [r[0] for r in rows],
            "node_name": [r[1] for r in rows],
            "metric": [r[2] for r in rows],
            "value": [float(r[3]) for r in rows],
            "definition": ["collab_v2"] * n,
        },
        schema={
            c: (
                pl.Date
                if c.startswith("period")
                else pl.Int64
                if c == "level"
                else pl.Float64
                if c == "value"
                else pl.String
            )
            for c in PANEL_COLUMNS
        },
    )


INDEX = TaskIndex({"draft memos": [1]}, {1: ["11-1011.00", "11-1021.00"]})
PANEL = _panel([("1", "draft memos", "pct", 10), ("1", "draft memos", "automation_pct", 40)])


def _national(e1, e2):
    return pl.DataFrame(
        {"soc6": ["11-1011", "11-1021"], "tot_emp": [e1, e2]},
        schema={"soc6": pl.String, "tot_emp": pl.Int64},
    )


def _row(t, soc):
    return t.filter(pl.col("soc6") == soc).row(0, named=True)


def test_employment_allocation_hand_computed():
    from aideleg.occupations import COLUMNS

    t = employment_allocation_table(PANEL, "r2", INDEX, _national(300, 100), soc_structure=None)
    assert t.columns == COLUMNS
    assert _row(t, "11-1011")["usage_pct_all"] == pytest.approx(7.5)
    assert _row(t, "11-1021")["usage_pct_all"] == pytest.approx(2.5)
    assert t["usage_share"].sum() == pytest.approx(100.0)
    assert _row(t, "11-1011")["automation_pct"] == pytest.approx(40.0)
    assert _row(t, "11-1021")["automation_pct"] == pytest.approx(40.0)


def test_employment_allocation_equal_when_no_employment():
    t = employment_allocation_table(PANEL, "r2", INDEX, _national(None, None), soc_structure=None)
    assert _row(t, "11-1011")["usage_pct_all"] == pytest.approx(5.0)
    assert _row(t, "11-1021")["usage_pct_all"] == pytest.approx(5.0)


def test_employment_allocation_shared_oews_code_divides():
    # 11-1011 and 11-1012 both resolve to OEWS 11-1010 (rollup): each gets half its employment
    idx = TaskIndex({"draft memos": [1]}, {1: ["11-1011.00", "11-1012.00", "11-1021.00"]})
    nat = pl.DataFrame({"soc6": ["11-1010", "11-1021"], "tot_emp": [200, 100]})
    t = employment_allocation_table(PANEL, "r2", idx, nat, soc_structure=None)
    assert _row(t, "11-1011")["usage_pct_all"] == pytest.approx(10 * 100 / 300)
    assert _row(t, "11-1012")["usage_pct_all"] == pytest.approx(10 * 100 / 300)
    assert _row(t, "11-1021")["usage_pct_all"] == pytest.approx(10 * 100 / 300)


COLS = ["NAICS", "NAICS_TITLE", "OWN_CODE", "OCC_CODE", "O_GROUP", "TOT_EMP", "A_MEAN"]


def _xlsx(path: Path, rows: list[tuple]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(COLS)
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return path


def test_wage_bill_topcode_and_suppression(tmp_path):
    p = _xlsx(
        tmp_path / "nat4d.xlsx",
        [
            ("111100", "Ind", "5", "00-0000", "total", "30", "80000"),
            ("111100", "Ind", "5", "11-1011", "detailed", "10", "#"),
            ("111100", "Ind", "5", "11-1021", "detailed", "10", "*"),
            ("111100", "Ind", "5", "15-1252", "detailed", "10", "100000"),
        ],
    )
    m = wage_bill_matrix(2024, path=p)
    assert m.columns == ["naics", "naics_title", "soc6", "tot_emp", "emp_share_in_industry"]
    wb = dict(zip(m["soc6"], m["tot_emp"], strict=True))
    assert wb["11-1011"] == pytest.approx(2_392_000.0)
    assert wb["11-1021"] is None
    assert wb["15-1252"] == pytest.approx(1_000_000.0)
    sh = dict(zip(m["soc6"], m["emp_share_in_industry"], strict=True))
    assert sh["11-1011"] == pytest.approx(2_392_000 / 3_392_000)
    assert sh["11-1011"] == pytest.approx(0.70519, abs=1e-5)
    assert sh["15-1252"] == pytest.approx(0.29481, abs=1e-5)
    assert sh["11-1021"] is None
    assert wage_bill_coverage(2024, path=p) == pytest.approx(20 / 30)


def _split6(rows):
    return pl.DataFrame(
        rows, schema={"naics": pl.String, "ff49": pl.Int64, "weight": pl.Float64}, orient="row"
    )


def _pub(rows):
    return pl.DataFrame(
        rows, schema={"naics": pl.String, "level": pl.Int64, "emp": pl.Float64}, orient="row"
    )


def _tot(rows):
    return pl.DataFrame(rows, schema={"naics": pl.String, "emp": pl.Float64}, orient="row")


def _w(xw, naics):
    sub = xw.filter(pl.col("naics") == naics)
    return dict(zip(sub["ff49"], sub["weight"], strict=True))


def test_emp_weighted_crosswalk_hand_computed():
    s6 = _split6(
        [
            ("111110", 1, 1.0),
            ("111120", 2, 1.0),
            ("111210", 1, 0.5),
            ("111210", 2, 0.5),
            ("111220", 2, 1.0),
        ]
    )
    pub = _pub([("111110", 6, 300.0), ("111120", 6, 100.0)])
    xw = emp_weighted_naics_ff49(split6=s6, published=pub, totals=_tot([("1111", 400.0)]))
    w = _w(xw, "1111")
    assert w[1] == pytest.approx(0.75)
    assert w[2] == pytest.approx(0.25)
    # 1112 has no published child: the primary equal split
    w2 = _w(xw, "1112")
    assert w2[1] == pytest.approx(0.25)
    assert w2[2] == pytest.approx(0.75)
    assert xw.group_by("naics").agg(pl.col("weight").sum())["weight"].to_list() == pytest.approx(
        [1.0, 1.0]
    )


def test_emp_weighted_residual_rule():
    s6 = _split6([("111110", 1, 1.0), ("111120", 2, 1.0), ("111130", 3, 1.0)])
    pub = _pub([("111110", 6, 300.0)])
    xw = emp_weighted_naics_ff49(split6=s6, published=pub, totals=_tot([("1111", 500.0)]))
    w = _w(xw, "1111")
    assert w == pytest.approx({1: 300 / 500, 2: 100 / 500, 3: 100 / 500})


def test_emp_weighted_five_digit_split_and_negative_residual():
    # 11112 (5-digit) is published at 100 and split over 111121, 111122; E4 below the
    # published sum leaves the unpublished 111130 with max(90 - 400, 0) = 0
    s6 = _split6([("111110", 1, 1.0), ("111121", 2, 1.0), ("111122", 3, 1.0), ("111130", 4, 1.0)])
    pub = _pub([("111110", 6, 300.0), ("111120", 5, 100.0)])
    xw = emp_weighted_naics_ff49(split6=s6, published=pub, totals=_tot([("1111", 90.0)]))
    w = _w(xw, "1111")
    assert w[1] == pytest.approx(0.75)
    assert w[2] == pytest.approx(0.125)
    assert w[3] == pytest.approx(0.125)
    assert w.get(4, 0.0) == pytest.approx(0.0)


def test_emp_weighted_excludes_hq():
    s6 = _split6([("551111", 48, 1.0), ("111110", 1, 1.0)])
    xw = emp_weighted_naics_ff49(split6=s6, published=_pub([]), totals=_tot([]))
    assert "5511" not in xw["naics"].to_list()


@pytest.mark.data
def test_emp_weighted_default_equals_split_where_unpublished():
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49

    xw = emp_weighted_naics_ff49()
    base = naics_to_ff49()
    assert set(xw["naics"]) == set(base["naics"])
    j = xw.join(
        base, on=["naics", "ff49"], how="full", nulls_equal=True, coalesce=True, suffix="_b"
    )
    pub = _published_n4()
    # an n4 code without a published child keeps the primary equal split exactly
    unpub = j.filter(~pl.col("naics").is_in(pub))
    assert (unpub["weight"] == unpub["weight_b"]).all()
    # 2211 (eight published 6-digit generation codes) moves
    d = j.filter(pl.col("naics").is_in(pub))
    assert ((d["weight"].fill_null(0) - d["weight_b"].fill_null(0)).abs() > 1e-9).any()


def _published_n4() -> list[str]:
    from aideleg.robustness.inputs import _published

    return sorted(set(_published()["naics"].str.slice(0, 4)))


@pytest.mark.data
def test_bls_crosswalk_covers_aioe():
    from aideleg.benchmarks import _structure, coverage, load_aioe
    from aideleg.bls.oews import load_national

    xw = bls_soc_crosswalk()
    assert xw.columns == ["o2010", "o2019"]
    assert xw["o2010"].str.contains(r"^\d{2}-\d{4}$").all()
    assert xw["o2019"].str.contains(r"^\d{2}-\d{4}$").all()
    a = load_aioe(crosswalk=xw)
    assert coverage(a, load_national(2024), _structure()) >= 0.9


@pytest.mark.data
def test_index_29_2_builds():
    idx = index_29_2()
    assert sum(idx.provenance().values()) == len(idx._occ_by_id) + idx.provenance()["unresolved"]
    assert idx.provenance()["onet_2019"] > 0


@pytest.mark.data
def test_consequence_of_error_and_public_float():
    from aideleg.robustness.inputs import consequence_of_error, public_float

    coe = consequence_of_error()
    assert coe.columns == ["soc6", "coe"]
    assert coe["soc6"].is_unique().all()
    assert coe["coe"].is_between(1, 5).all()
    pf = public_float()
    assert pf.columns == ["cik", "public_float_usd"]
    assert pf["cik"].is_unique().all()
    assert pf.height > 4000


WIRED = {
    "wage_bill": {"weights": "wage_bill"},
    "employment_allocation": {"allocation": "employment"},
    "emp_weighted": {"crosswalk": "emp_weighted"},
    "aioe_bls": {"aioe_crosswalk": "bls"},
}


@pytest.mark.data
@pytest.mark.parametrize("name", sorted(WIRED))
def test_wired_options_run_and_move(name):
    from aideleg.robustness.exposure_variants import ExposureSpec, variant_exposure

    base = variant_exposure(ExposureSpec())
    var = variant_exposure(ExposureSpec(**WIRED[name]))
    assert var.height == 49
    assert var.select(pl.col("^z_.*$").null_count()).sum_horizontal().item() == 0
    j = base.join(var, on="industry", suffix="_v")
    col = "z_aioe" if name == "aioe_bls" else "z_delegation"
    assert (j[col] - j[f"{col}_v"]).abs().max() > 1e-3
    if name == "aioe_bls":  # R14 replaces AIOE only
        assert (j["z_delegation"] == j["z_delegation_v"]).all()


@pytest.mark.data
def test_onet_29_2_reproduces_primary():
    # the downloaded 29.2 task statements are byte-identical to 29.3, so R32's O*NET part
    # cannot move the vector (the R32 notes say so)
    from aideleg.robustness.exposure_variants import ExposureSpec, variant_exposure, vector_hash

    assert vector_hash(variant_exposure(ExposureSpec(onet="29.2"))) == vector_hash(
        variant_exposure(ExposureSpec())
    )
