"""Guarded loaders on fixtures and synthetic data. No real market data is read."""

from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg import confirm_h5, power
from aideleg.market import french, seal
from aideleg.rq3 import data, guard

FX = Path(__file__).parent.parent / "fixtures" / "french"


@pytest.fixture
def fixture_file(monkeypatch):
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    monkeypatch.setattr(data, "_monthly_file", lambda: FX / "ind_monthly_small.csv")
    monkeypatch.setattr(guard, "assert_confirmatory_recorded", lambda repo=None: None)


def test_read_french_annual_reads_beme_table():
    df = data.read_french_annual(FX / "ind_monthly_small.csv", "Sum of BE / Sum of ME")
    assert df.columns == ["year", "Agric", "Food"]
    assert df["year"].to_list() == [2023, 2024]
    assert df["year"].dtype == pl.Int64
    assert df["Food"].to_list() == [0.40, None]


def test_read_french_annual_missing_title_raises():
    with pytest.raises(ValueError, match="not found"):
        data.read_french_annual(FX / "ind_monthly_small.csv", "No such table")


def test_characteristics_cap_is_firms_times_size(fixture_file):
    ch = data.characteristics()
    assert ch.columns == ["date", "me_date", "ff49_short", "n_firms", "avg_size", "cap"]
    a = ch.filter((pl.col("ff49_short") == "Agric") & (pl.col("date") == date(2024, 1, 31)))
    assert a["cap"].to_list() == [26.0]
    f = ch.filter((pl.col("ff49_short") == "Food") & (pl.col("date") == date(2024, 1, 31)))
    assert f["cap"].to_list() == [None]


@pytest.mark.parametrize("offset,expected", [(1, date(2023, 12, 31)), (0, date(2024, 1, 31))])
def test_characteristics_me_date_follows_offset(fixture_file, monkeypatch, offset, expected):
    monkeypatch.setattr(data, "SIZE_ME_OFFSET", offset)
    ch = data.characteristics().filter(
        (pl.col("ff49_short") == "Agric") & (pl.col("date") == date(2024, 1, 31)))
    assert ch["me_date"].to_list() == [expected]


def test_size_me_offset_is_the_verified_value():
    assert data.SIZE_ME_OFFSET == 1


def test_beme_long_and_nonpositive_null(fixture_file):
    b = data.beme()
    assert b.columns == ["year", "ff49_short", "beme"]
    got = {(r["year"], r["ff49_short"]): r["beme"] for r in b.iter_rows(named=True)}
    assert got[(2023, "Agric")] == 0.50 and got[(2024, "Food")] is None


def test_beme_sets_nonpositive_to_null(fixture_file, monkeypatch):
    monkeypatch.setattr(
        data, "read_french_annual",
        lambda p, t: pl.DataFrame({"year": [2023], "Agric": [-0.3], "Food": [0.0]}))
    assert data.beme()["beme"].to_list() == [None, None]


def _boom(*a, **k):
    pytest.fail("a French loader ran before the guard")


def _refuse(repo=None):
    raise guard.ConfirmatoryNotRecorded("not committed")


def test_post_seal_loaders_call_the_guard_first(monkeypatch):
    monkeypatch.setattr(guard, "assert_confirmatory_recorded", _refuse)
    for name in ("load_industry_returns", "load_factors", "read_french_table", "_single_file"):
        monkeypatch.setattr(french, name, _boom)
    monkeypatch.setattr(data, "read_french_annual", _boom)
    for fn in (data.daily, data.monthly, data.ff3_monthly, data.characteristics, data.beme):
        with pytest.raises(guard.ConfirmatoryNotRecorded):
            fn()


def test_loaders_pass_end_and_weighting(monkeypatch):
    monkeypatch.setattr(guard, "assert_confirmatory_recorded", lambda repo=None: None)
    seen = []
    monkeypatch.setattr(
        french, "load_industry_returns",
        lambda freq, w, end: seen.append(("ind", freq, w, end)) or pl.DataFrame())
    monkeypatch.setattr(
        french, "load_factors", lambda freq, end: seen.append(("fac", freq, end)) or pl.DataFrame())
    data.daily("EW")
    data.monthly()
    assert seen == [("ind", "D", "EW", data.MARKET_END), ("fac", "D", data.MARKET_END),
                    ("ind", "M", "VW", data.MARKET_END), ("fac", "M", data.MARKET_END)]
    assert data.MARKET_END == date(2026, 8, 31)


def test_ff3_monthly_columns_and_end(monkeypatch):
    monkeypatch.setattr(guard, "assert_confirmatory_recorded", lambda repo=None: None)
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    monkeypatch.setattr(french, "_single_file", lambda key: FX / "ff3_small.csv")
    ff3 = data.ff3_monthly()
    assert ff3.columns == ["date", "mkt_rf", "smb", "hml", "rf"]
    assert ff3["date"].max() <= data.MARKET_END
    assert ff3.height == 2


def test_exposures_refuse_on_hash_mismatch(monkeypatch):
    names = [f"I{i:02d}" for i in range(1, 50)]
    expo = pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": names,
                         "z_delegation": [float(i) for i in range(49)],
                         "z_aioe": [float(-i) for i in range(49)]})
    bumped = expo.with_columns(
        pl.when(pl.col("ff49") == 1).then(pl.col("z_delegation") + 1e-6)
        .otherwise(pl.col("z_delegation")).alias("z_delegation"))
    monkeypatch.setattr(power, "load_exposure", lambda: bumped)
    with pytest.raises(ValueError, match="EXPOSURE_SHA256"):
        data.exposures()


@pytest.mark.data
def test_exposures_have_three_designs():
    ex = data.exposures()
    assert ex.columns == ["design", "ff49", "ff49_short", "z_delegation", "z_usage", "z_aioe"]
    assert set(ex["design"]) == {"B", "A_r2", "A_pooled"}
    assert ex.group_by("design").len()["len"].to_list() == [49, 49, 49]
    b = ex.filter(pl.col("design") == "B").sort("ff49")["z_delegation"]
    a = ex.filter(pl.col("design") == "A_r2").sort("ff49")["z_delegation"]
    assert a.to_list() == b.to_list()


@pytest.mark.data
def test_zero_assigned_has_three_designs_and_reads_no_market_data(monkeypatch):
    monkeypatch.setattr(guard, "assert_confirmatory_recorded", _refuse)
    z = data.zero_assigned()
    assert z.columns == ["design", "occupations", "no_usage", "no_usage_emp_pct"]
    assert set(z["design"]) == {"B", "A_pooled", "A_r2"}


def test_hash_constant_is_the_confirmatory_one():
    assert len(confirm_h5.EXPOSURE_SHA256) == 64
