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


def test_monthly_dates_parse_to_month_end(monkeypatch):
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
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


def test_sealed_rows_dropped_unless_frozen(monkeypatch):
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)
    df = french.read_french_table(
        FX / "ind_monthly_small.csv", "Average Value Weighted Returns -- Monthly"
    )
    assert df.height == 0
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    df = french.read_french_table(
        FX / "ind_monthly_small.csv", "Average Value Weighted Returns -- Monthly"
    )
    assert df.height == 2


def test_wrong_column_count_raises_with_line(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("  T\n,A,B\n20200102, 1.0, 2.0\n20200103, 1.0\n")
    with pytest.raises(ValueError, match=r"bad\.csv:4"):
        french.read_french_table(f, "T")


def test_non_numeric_cell_raises_with_line(tmp_path):
    f = tmp_path / "bad.csv"
    f.write_text("  T\n,A,B\n20200102, 1.0, 2.0\n20200103, x, 1.0\n")
    with pytest.raises(ValueError, match=r"bad\.csv:4"):
        french.read_french_table(f, "T")


def _point_at_fixtures(monkeypatch, mapping):
    monkeypatch.setattr(french, "_single_file", lambda key: FX / mapping[key])


def test_load_factors_join_rename_order_and_filter(monkeypatch, tmp_path):
    ff5 = tmp_path / "ff5.csv"
    ff5.write_text(
        "\n,Mkt-RF,SMB,HML,RMW,CMA,RF\n"
        "20220101, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0\n"
        "20220102, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5\n"
        "20220103, 9.0, 9.0, 9.0, 9.0, 9.0, 9.0\n"
    )
    mom = tmp_path / "mom.csv"
    mom.write_text("\n,Mom\n20220101, 7.0\n20220102, -99.99\n20220103, 8.0\n")
    monkeypatch.setattr(
        french, "_single_file", lambda key: ff5 if key.startswith("ff5") else mom
    )
    df = french.load_factors("D", date(2022, 1, 2))
    assert df.columns == ["date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf", "umd"]
    assert df["date"].to_list() == [date(2022, 1, 1), date(2022, 1, 2)]
    assert df.row(0) == (date(2022, 1, 1), 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0)
    assert df["umd"][1] is None


def test_load_industry_returns_happy_path(monkeypatch):
    _point_at_fixtures(monkeypatch, {"ff49_daily": "ind_daily_small.csv"})
    df = french.load_industry_returns("D", "EW", date(2020, 1, 2))
    assert df.columns == ["date", "Agric", "Food"]
    assert df.height == 1
    assert df["Agric"].to_list() == [0.40]
    vw = french.load_industry_returns("D", "VW", date(2020, 1, 31))
    assert vw.height == 3


@pytest.mark.parametrize("n", [0, 2])
def test_single_file_requires_exactly_one(monkeypatch, tmp_path, n):
    from aideleg.acquire import sources

    class S:
        dest = "french/x.zip"

    monkeypatch.setattr(sources, "by_key", lambda key: S())
    monkeypatch.setattr(french, "RAW", tmp_path)
    d = tmp_path / "french" / "x"
    d.mkdir(parents=True)
    for i in range(n):
        (d / f"f{i}.csv").write_text("")
    with pytest.raises(FileNotFoundError):
        french._single_file("k")


def test_parsing_stops_at_the_first_sealed_row_unless_frozen(monkeypatch, tmp_path):
    # K6: rows dated on or after the seal are never parsed before pap-v1, so a malformed
    # sealed row (wrong field count, non-numeric cell) cannot even raise
    f = tmp_path / "t.csv"
    f.write_text("  T\n,A,B\n20221128, 1.0, 2.0\n20221129, 3.0, 4.0\n"
                 "20221130, x\n20221201, 5.0, 6.0\n")
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)
    df = french.read_french_table(f, "T")
    assert df["date"].to_list() == [date(2022, 11, 28), date(2022, 11, 29)]
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    with pytest.raises(ValueError, match=r"t\.csv:5"):
        french.read_french_table(f, "T")
