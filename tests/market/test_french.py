from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg.market import french, seal

FX = Path(__file__).parent.parent / "fixtures" / "french"


def test_reads_only_requested_table():
    df = french.read_french_table(
        FX / "ind_daily_small.csv", "Average Value Weighted Returns -- Daily"
    )
    assert df.height == 3
    assert df.columns == ["date", "Agric", "Food"]
    assert df["Agric"][1] is None
    assert df["date"][0] == date(2020, 1, 2)
    assert df["Agric"].dtype == pl.Float64


def test_second_table_is_distinct():
    df = french.read_french_table(
        FX / "ind_daily_small.csv", "Average Equal Weighted Returns -- Daily"
    )
    assert df.height == 2
    assert df["Agric"].to_list() == [0.40, 0.30]


def test_monthly_dates_parse_to_month_end():
    df = french.read_french_table(
        FX / "ind_monthly_small.csv", "Average Value Weighted Returns -- Monthly"
    )
    assert df["date"].to_list() == [date(2023, 1, 31), date(2023, 2, 28)]


def test_untitled_first_table_and_annual_ignored():
    df = french.read_french_table(FX / "factors_small.csv", "")
    assert df.columns == ["date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"]
    assert df.height == 2
    assert df["SMB"][1] is None


def test_missing_title_raises():
    with pytest.raises(ValueError):
        french.read_french_table(FX / "ind_daily_small.csv", "No Such Table")


def test_load_industry_returns_checks_seal_before_reading(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise AssertionError("read_french_table was called")

    monkeypatch.setattr(french, "read_french_table", boom)
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)
    with pytest.raises(seal.SealedPeriodError):
        french.load_industry_returns("D", "VW", date(2025, 1, 1))


def _boom(*a, **k):
    raise AssertionError("read_french_table was called")


def test_load_factors_checks_seal_first(monkeypatch):
    monkeypatch.setattr(french, "read_french_table", _boom)
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)
    with pytest.raises(seal.SealedPeriodError):
        french.load_factors("M", date(2026, 8, 31))


def test_siccodes_ranges():
    df = french.read_siccodes(FX / "siccodes_small.txt")
    assert df.columns == ["ff49", "ff49_short", "ff49_name", "sic_lo", "sic_hi"]
    assert df.height == 5
    assert (df["sic_lo"] <= df["sic_hi"]).all()
    row = df.filter((df["sic_lo"] == 100) & (df["sic_hi"] == 199))
    assert row["ff49_short"].to_list() == ["Agric"]
    assert row["ff49_name"].to_list() == ["Agriculture"]
    assert df.filter(df["ff49"] == 2).height == 2
