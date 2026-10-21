import polars as pl
import pytest

from aideleg.config import RAW
from aideleg.crosswalk.naics_ff49 import (
    NO_PUBLIC_EQUITY,
    chain_links,
    coverage_by_code,
    coverage_report,
    invert,
    majority,
    naics_to_ff49,
    naics_to_sic,
    oews_components,
    oews_status,
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
        ("491100", "Postal Service (Federal Government)", "43-5052", 60),  # NO_PUBLIC_EQUITY
        ("455000", "General Merchandise Retailers", "41-2031", 20),  # 4551 mapped, 4552 not
        ("551100", "Management of Companies and Enterprises", "11-1021", 50),
        ("999100", "Federal Executive Branch (OEWS Designation)", "13-1071", 300),
        ("999300", "Local Government (OEWS Designation)", "33-3051", None),
    ])
    rep = {r["status"]: r for r in coverage_report(m, crosswalk=XW).iter_rows(named=True)}
    assert set(rep) == {"mapped", "unmapped", "government", "management_of_companies"}
    assert rep["government"]["tot_emp"] == 360  # 99xxxx + USPS
    assert rep["government"]["share_of_private"] is None
    assert rep["management_of_companies"]["tot_emp"] == 50
    assert rep["management_of_companies"]["share_of_private"] is None
    assert rep["mapped"]["tot_emp"] == pytest.approx(140)
    assert rep["unmapped"]["tot_emp"] == pytest.approx(20)  # 10 banks + 10 retail
    assert rep["unmapped"]["share_of_private"] == pytest.approx(20 / 160)
    assert rep["mapped"]["share_of_total"] == pytest.approx(140 / 570)


def test_usps_is_no_public_equity():
    assert "491100" in NO_PUBLIC_EQUITY
    assert oews_status("491100") == "government"
    assert oews_status("999200") == "government"
    assert oews_status("491200") == "private"
    assert oews_status("551100") == "management_of_companies"
    assert oews_status("551100", hq="redistribute") == "private"


def test_overlapping_oews_codes_raise():
    m = _matrix([("5220A1", "Credit (5221 and 5223 only)", "43-3071", 10),
                 ("522100", "Depository", "43-3071", 40)])
    with pytest.raises(ValueError, match="both cover"):
        coverage_by_code(m, crosswalk=XW)


def test_three_digit_rule_guard():
    xw = pl.concat([XW, pl.DataFrame({"naics": ["4550"], "ff49": [43], "weight": [1.0]},
                                     schema=XW.schema)])
    m = _matrix([("455000", "General Merchandise Retailers", "41-2031", 20)])
    with pytest.raises(ValueError, match="xxx000"):
        coverage_by_code(m, crosswalk=xw)


def test_residuals_rounded():
    xw = pl.DataFrame({"naics": ["5112"] * 3, "ff49": [36, 34, 35],
                       "weight": [0.1, 0.2, 0.7]}, schema=XW.schema)
    m = _matrix([("511200", "Software Publishers", "15-1252", 1_000_000)])
    assert coverage_by_code(m, crosswalk=xw)["unmapped_emp"].to_list() == [0.0]


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
    m = load_industry_matrix(2024, 4)
    rep = coverage_report(m)
    with capsys.disabled():
        print("\n", rep)
        print(coverage_by_code(m).filter(pl.col("unmapped_emp") > 0)
              .sort("unmapped_emp", descending=True).head(15))
    share = rep.filter(pl.col("status") == "unmapped")["share_of_private"].sum()
    assert share < 0.01, coverage_by_code(m).sort("unmapped_emp", descending=True).head(20)


@pytest.mark.data
@_needs_raw
def test_sourceless_codes_kept_unmapped():
    six = naics_to_ff49("split", digits=6, hq="redistribute",
                        employment=_matrix([("522100", "Depository", "43-3071", 1)]))
    assert "551114" in set(six["naics"])
    for code in ("112130", "481219", "541120"):
        rows = six.filter(pl.col("naics") == code)
        assert rows["ff49"].to_list() == [None] and rows["weight"].to_list() == [1.0]


@pytest.mark.data
@_needs_raw
def test_hq_excluded_by_default():
    for digits in (4, 6):
        ff = naics_to_ff49("split", digits=digits)
        assert ff.filter(pl.col("naics").str.starts_with("5511")).is_empty()


@pytest.mark.data
@_needs_raw
def test_hq_redistribute_follows_employment():
    emp = _matrix([("522100", "Depository Credit Intermediation", "43-3071", 300),
                   ("513200", "Software Publishers", "15-1252", 100),
                   ("999100", "Federal Executive Branch (OEWS Designation)", "13-1071", 900),
                   ("491100", "Postal Service (Federal Government)", "43-5052", 900)])
    for method in ("split", "majority"):
        ff = naics_to_ff49(method, hq="redistribute", employment=emp)
        hq = ff.filter(pl.col("naics") == "5511")
        assert dict(hq.select("ff49", "weight").iter_rows()) == pytest.approx({36: 0.25, 45: 0.75})
        rep = coverage_report(emp.vstack(_matrix([("551100", "Mgmt", "11-1021", 40)])),
                              method, "redistribute", employment=emp)
        rep = dict(rep.select("status", "tot_emp").iter_rows())
        assert rep["management_of_companies"] == 0 and rep["mapped"] == pytest.approx(440)
