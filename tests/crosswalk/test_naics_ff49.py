import polars as pl
import pytest

from aideleg.config import RAW
from aideleg.crosswalk.naics_ff49 import (
    chain_links,
    coverage_report,
    invert,
    majority,
    naics_to_ff49,
    naics_to_sic,
    oews_components,
    sic_to_ff49,
)

SICCODES = pl.DataFrame(
    {
        "ff49": [36, 36, 45, 49],
        "ff49_short": ["Softw", "Softw", "Banks", "Other"],
        "ff49_name": ["Computer Software", "Computer Software", "Banking", "Almost Nothing"],
        "sic_lo": [7372, 7375, 6020, 4950],
        "sic_hi": [7372, 7375, 6029, 4959],
    }
)


def _link(pairs):
    return pl.DataFrame(pairs, schema={"src": pl.String, "dst": pl.String}, orient="row")


# --- unit ------------------------------------------------------------------------------

def test_chain_splits_equally_and_composes():
    a = _link([("7372", "511210"), ("7372", "334611"), ("6021", "522110")])
    b = _link([("511210", "513210"), ("334611", "334610"), ("522110", "522110")])
    out = chain_links([a, b]).sort("src", "dst")
    w = {(r["src"], r["dst"]): r["weight"] for r in out.iter_rows(named=True)}
    assert w == {("6021", "522110"): 1.0, ("7372", "334610"): 0.5, ("7372", "513210"): 0.5}


def test_chain_uses_explicit_share_column():
    a = _link([("1", "x"), ("1", "y")]).with_columns(share=pl.Series([0.8, 0.2]))
    out = chain_links([a]).sort("dst")
    assert out["weight"].to_list() == pytest.approx([0.8, 0.2])


def test_weights_sum_to_one_after_invert():
    a = _link([("7372", "511210"), ("7372", "334611"), ("7371", "511210"), ("6021", "522110")])
    inv = invert(chain_links([a]))
    sums = inv.group_by("naics").agg(s=pl.col("weight").sum())
    assert sums["s"].to_list() == pytest.approx([1.0] * sums.height)
    # 511210 receives half of 7372 and all of 7371 -> 1/3 and 2/3
    w = dict(inv.filter(pl.col("naics") == "511210").select("sic", "weight").iter_rows())
    assert w == pytest.approx({7372: 1 / 3, 7371: 2 / 3})


def test_majority_takes_largest_share_unmapped_included():
    split = pl.DataFrame({"naics": ["4911", "4911", "5221", "5221", "5221"],
                          "ff49": [34, None, 45, 48, None], "weight": [0.03, 0.97, 0.4, 0.4, 0.2]},
                         schema={"naics": pl.String, "ff49": pl.Int64, "weight": pl.Float64})
    got = {n: (f, w) for n, f, w in majority(split).iter_rows()}
    assert got == {"4911": (None, 1.0), "5221": (45, 1.0)}  # tie -> lower industry number


def test_sic_to_ff49_only_listed_ranges():
    f = sic_to_ff49(SICCODES)
    assert f(7372) == 36 and f(6025) == 45 and f(4955) == 49
    assert f(7373) is None  # outside every range: unmapped, not "Other"
    assert f(4311) is None


def test_oews_components():
    assert oews_components("511200", "Software Publishers") == ["5112"]
    assert oews_components("455000", "General Merchandise Retailers") == ["455"]  # 3-digit
    assert oews_components("3250A1", "Chemical Manufacturing (3251, 3252, 3253, and 3259 only)") \
        == ["3251", "3252", "3253", "3259"]
    assert oews_components("5220A1", "Credit (5221 and 5223 only)") == ["5221", "5223"]
    with pytest.raises(ValueError):
        oews_components("3250A9", "Chemical Manufacturing")  # no component list
    assert oews_components("999100", "Federal Executive Branch (OEWS Designation)") is None


def _matrix(rows):
    return pl.DataFrame(rows, schema={"naics": pl.String, "naics_title": pl.String,
                                      "soc6": pl.String, "tot_emp": pl.Int64}, orient="row")


XW = pl.DataFrame({"naics": ["5112", "5221", "5221", "4911", "4551", "4552"],
                   "ff49": [36, 45, None, None, 43, None],
                   "weight": [1.0, 0.75, 0.25, 1.0, 1.0, 1.0]},
                  schema={"naics": pl.String, "ff49": pl.Int64, "weight": pl.Float64})


def test_government_excluded_not_unmapped():
    m = _matrix([
        ("511200", "Software Publishers", "15-1252", 100),
        ("522100", "Depository", "43-3071", 40),
        ("491100", "Postal Service (Federal Government)", "43-5052", 60),
        ("455000", "General Merchandise Retailers", "41-2031", 20),  # 4551 mapped, 4552 not
        ("999100", "Federal Executive Branch (OEWS Designation)", "13-1071", 300),
        ("999300", "Local Government (OEWS Designation)", "33-3051", None),
    ])
    rep = {r["status"]: r for r in coverage_report(m, crosswalk=XW).iter_rows(named=True)}
    assert set(rep) == {"mapped", "unmapped", "government"}
    assert rep["government"]["tot_emp"] == 300
    assert rep["government"]["share_of_private"] is None
    assert rep["mapped"]["tot_emp"] == pytest.approx(140)
    assert rep["unmapped"]["tot_emp"] == pytest.approx(80)  # 10 banks + 60 postal + 10 retail
    assert rep["unmapped"]["share_of_private"] == pytest.approx(80 / 220)
    assert rep["mapped"]["share_of_total"] == pytest.approx(140 / 520)


# --- real data -------------------------------------------------------------------------

_CENSUS = RAW / "census"
_needs_raw = pytest.mark.skipif(
    not (_CENSUS / "2017_to_2022_NAICS.xlsx").exists()
    or not (RAW / "french/Siccodes49").exists(),
    reason="needs data/raw (run `make data`)",
)


@pytest.mark.data
@_needs_raw
def test_weights_sum_to_one():
    xw = naics_to_sic(2022)
    assert xw.columns == ["naics", "sic", "weight"]
    sums = xw.group_by("naics").agg(s=pl.col("weight").sum())
    assert sums["s"].min() == pytest.approx(1.0) and sums["s"].max() == pytest.approx(1.0)
    assert sums.height > 900  # most of the ~1,000 NAICS 2022 national industries
    ff = naics_to_ff49("split")
    s = ff.group_by("naics").agg(s=pl.col("weight").sum())  # null ff49 = unmapped share
    assert s["s"].min() == pytest.approx(1.0) and s["s"].max() == pytest.approx(1.0)


@pytest.mark.data
@_needs_raw
def test_known_mappings():
    from aideleg.market.french import _single_file, read_siccodes

    short = dict(read_siccodes(_single_file("ff_siccodes49"))
                 .select("ff49", "ff49_short").unique().iter_rows())
    ff = naics_to_ff49("majority").filter(pl.col("ff49").is_not_null())
    got = {n: short[f] for n, f in ff.select("naics", "ff49").iter_rows()}
    software = got.get("5132", got.get("5112"))  # 2017 5112 became 2022 5132
    assert software == "Softw"
    assert got["5221"] == "Banks"
    assert got["3254"] == "Drugs"
    assert got["4841"] == "Trans"
    assert got["5241"] == "Insur"


@pytest.mark.data
@pytest.mark.skipif(not (RAW / "bls/oesm24in4").exists(), reason="needs OEWS 2024")
@_needs_raw
def test_unmapped_private_employment_below_1pct(capsys):
    from aideleg.bls.oews import load_industry_matrix
    from aideleg.crosswalk.naics_ff49 import coverage_by_code

    m = load_industry_matrix(2024, 4)
    rep = coverage_report(m)
    with capsys.disabled():
        print("\n", rep)
        print(coverage_by_code(m).filter(pl.col("unmapped_emp") > 0)
              .sort("unmapped_emp", descending=True).head(15))
    share = rep.filter(pl.col("status") == "unmapped")["share_of_private"].sum()
    assert share < 0.01, coverage_by_code(m).sort("unmapped_emp", descending=True).head(20)
