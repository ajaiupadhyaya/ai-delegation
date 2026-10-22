from pathlib import Path

import openpyxl
import polars as pl
import pytest

from aideleg.acquire.sources import by_key
from aideleg.bls.oews import (
    load_industry_matrix,
    load_national,
    oews_code_for,
)
from aideleg.config import DERIVED, RAW

COLS = ["AREA", "NAICS", "NAICS_TITLE", "I_GROUP", "OWN_CODE", "OCC_CODE", "OCC_TITLE",
        "O_GROUP", "TOT_EMP", "A_MEDIAN"]


def _xlsx(path: Path, rows: list[tuple]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(COLS)
    for r in rows:
        ws.append(list(r))
    wb.save(path)
    return path


def _row(naics, occ, group, emp, med="50000", title="T", own="5"):
    return ("99", naics, f"Ind {naics}", "4-digit", own, occ, title, group, emp, med)


IND_ROWS = [
    _row("111100", "00-0000", "total", "1000"),
    _row("111100", "11-0000", "major", "300"),
    _row("111100", "11-1011", "detailed", "100"),
    _row("111100", "11-1021", "detailed", "200"),
    _row("111100", "15-1250", "detailed", "**"),  # suppressed
    _row("111100", "15-1252", "detailed", "700"),
    _row("111200", "11-1011", "detailed", "30"),
    _row("111200", "15-1252", "detailed", "70"),
    _row("111300", "11-1011", "detailed", "**"),
    _row("111300", "11-1021", "detailed", "**"),
]


@pytest.fixture
def ind_path(tmp_path):
    return _xlsx(tmp_path / "nat4d_small.xlsx", IND_ROWS)


def test_suppressed_values_become_null(tmp_path):
    p = _xlsx(tmp_path / "nat.xlsx", [
        _row("000000", "11-1011", "detailed", "**", med="*", own="1235"),
        _row("000000", "11-1021", "detailed", "500", med="#", own="1235"),
        _row("000000", "15-1252", "detailed", "700", med="90000", own="1235"),
    ])
    nat = load_national(path=p).sort("soc6")
    assert nat["tot_emp"].to_list() == [None, 500, 700]
    assert nat["a_median"].to_list() == [None, None, 90000]
    assert nat.schema["tot_emp"] == pl.Int64 and nat.schema["a_median"] == pl.Float64


def test_only_detailed_occupations(ind_path, tmp_path):
    ind = load_industry_matrix(path=ind_path)
    assert set(ind["soc6"]) == {"11-1011", "11-1021", "15-1250", "15-1252"}
    nat = load_national(path=_xlsx(tmp_path / "n.xlsx", [
        _row("000000", "00-0000", "total", "10", own="1235"),
        _row("000000", "11-0000", "major", "5", own="1235"),
        _row("000000", "11-1010", "broad", "5", own="1235"),
        _row("000000", "11-1011", "detailed", "5", own="1235"),
    ]))
    assert nat["soc6"].to_list() == ["11-1011"]
    assert list(nat.columns) == ["soc6", "title", "tot_emp", "a_median"]


def test_shares_sum_to_one_per_industry(ind_path):
    ind = load_industry_matrix(path=ind_path)
    assert list(ind.columns) == ["naics", "naics_title", "soc6", "tot_emp",
                                 "emp_share_in_industry"]
    sums = ind.group_by("naics").agg(s=pl.col("emp_share_in_industry").sum())
    by = dict(zip(sums["naics"], sums["s"], strict=True))
    assert by["111100"] == pytest.approx(1.0)  # renormalised over the non-null rows
    assert by["111200"] == pytest.approx(1.0)
    r = ind.filter((pl.col("naics") == "111100") & (pl.col("soc6") == "15-1252")).row(
        0, named=True)
    assert r["emp_share_in_industry"] == pytest.approx(0.7)
    # suppressed row keeps a null share, and an all-suppressed industry has no weights
    assert ind.filter(pl.col("soc6") == "15-1250")["emp_share_in_industry"][0] is None
    assert ind.filter(pl.col("naics") == "111300")["emp_share_in_industry"].is_null().all()


def test_industry_depth_checks_one_ownership_per_naics(tmp_path):
    p = _xlsx(tmp_path / "bad.xlsx", [
        _row("111100", "11-1011", "detailed", "1", own="5"),
        _row("111100", "11-1021", "detailed", "1", own="1"),
    ])
    with pytest.raises(ValueError, match="ownership"):
        load_industry_matrix(path=p)


# --- oews_code_for -------------------------------------------------------------------

STRUCT = pl.DataFrame({"Detailed Occupation": [
    "25-9041", "25-9042", "25-9043", "25-9044", "25-9045", "25-9049", "51-2021", "51-2022",
    "51-2023", "51-2031", "53-1042", None]})
OEWS = {"15-1252", "15-1250", "25-9045", "25-9046", "25-9099", "51-2020", "11-1011"}


def test_oews_code_for_exact():
    assert oews_code_for("15-1252", OEWS, STRUCT) == "15-1252"


def test_oews_code_for_aggregate_rollup():
    assert oews_code_for("15-1254", OEWS, STRUCT) == "15-1250"
    assert oews_code_for("51-2022", OEWS, STRUCT) == "51-2020"


def test_oews_code_for_hybrid_in_broad_group():
    # 25-9046 is not a SOC 2018 detailed code, and is the only such OEWS code in 25-904
    assert oews_code_for("25-9042", OEWS, STRUCT) == "25-9046"
    assert oews_code_for("25-9049", OEWS, STRUCT) == "25-9046"


def test_oews_code_for_ambiguous_or_absent_is_none():
    assert oews_code_for("25-9042", OEWS | {"25-9047"}, STRUCT) is None  # two hybrids
    assert oews_code_for("29-1141", OEWS, STRUCT) is None
    # an OEWS code in the broad group that IS a SOC 2018 detailed code is not a hybrid
    assert oews_code_for("25-9042", {"25-9045"}, STRUCT) is None
    assert oews_code_for("25-9042", OEWS, None) is None  # no structure: step 3 is skipped


# --- real data -----------------------------------------------------------------------

PANEL_PATH = DERIVED / "aei_panel.parquet"


@pytest.mark.data
@pytest.mark.skipif(not RAW.exists() or not PANEL_PATH.exists(),
                    reason="needs data/raw and `make panel`")
def test_real_join_coverage():
    from aideleg.aei.tasks import default_index
    from aideleg.occupations import occupation_table, soc_rollup

    nat = load_national(2024).filter(pl.col("tot_emp").is_not_null())
    codes = set(nat["soc6"])
    panel = pl.read_parquet(PANEL_PATH).filter(pl.col("release") == "r6")
    occ = occupation_table(panel, "r6", default_index(), basis="published")
    use = occ.group_by("soc6").agg(u=pl.col("usage_pct_all").sum())
    struct = pl.read_csv(RAW / by_key("aei_soc_structure").dest)

    total_emp = nat["tot_emp"].sum()
    total_use = use["u"].sum()
    steps = {
        "rollup only": lambda s: (r if (r := soc_rollup(s, codes)) in codes else None),
        "rollup + hybrid": lambda s: oews_code_for(s, codes, struct),
    }
    out = {}
    for name, fn in steps.items():
        m = use.with_columns(oews=pl.col("soc6").map_elements(fn, return_dtype=pl.String))
        hit = set(m["oews"].drop_nulls())
        emp = nat.filter(pl.col("soc6").is_in(hit))["tot_emp"].sum()
        un = m.filter(pl.col("oews").is_null())
        out[name] = (emp / total_emp, un["u"].sum() / total_use, un.sort("u", descending=True))
    assert out["rollup + hybrid"][0] >= 0.80
    assert out["rollup + hybrid"][0] >= out["rollup only"][0]
