"""H6 denominator (PAP §6, D18): EDGAR full-index 10-K filers, SIC from the bulk submissions
file (C-40), SIC -> FF49 by the Siccodes49 ranges."""

import json
import shutil
import zipfile
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg.crosswalk.naics_ff49 import sic_to_ff49
from aideleg.h6 import edgar

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/sec"
FORM_SMALL = FIXTURES / "form_small.idx"

# A Siccodes49 extract: 7370-7379 -> 36 (Softw), 6770 -> 48 (Fin). 9999 lies in no range.
SICCODES = pl.DataFrame(
    {"ff49": [36, 48], "sic_lo": [7370, 6770], "sic_hi": [7379, 6770]},
    schema={"ff49": pl.Int64, "sic_lo": pl.Int64, "sic_hi": pl.Int64},
)
LOOKUP = sic_to_ff49(SICCODES)

SUBMISSIONS = {  # member name -> JSON body, as in the bulk submissions.zip
    "CIK0001234567.json": {"cik": "1234567", "sic": "7372", "name": "ALPHA  BETA HOLDINGS"},
    "CIK0003333333.json": {"cik": "3333333", "sic": "", "name": "DELTA TRUST"},
    "CIK0005555555.json": {"cik": "5555555", "sic": "9999", "name": "ZETA CO"},
    "CIK0001234567-submissions-001.json": {"accessionNumber": []},
}


def build_submissions_zip(path: Path) -> Path:
    """`submissions_small.zip`, built deterministically from the JSON literals above."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(SUBMISSIONS):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 22, 0, 0, 0))
            zf.writestr(info, json.dumps(SUBMISSIONS[name]))
    return path


@pytest.fixture
def submissions_zip(tmp_path: Path) -> Path:
    return build_submissions_zip(tmp_path / "submissions_small.zip")


def _raw_with_year(tmp_path: Path, year: int) -> Path:
    """A raw dir whose QTR1 is the fixture and QTR2-4 hold only the preamble."""
    raw = tmp_path / "raw"
    head = "\n".join(FORM_SMALL.read_text().split("\n")[:10]) + "\n"
    for q in range(1, 5):
        d = raw / f"sec/full-index/{year}/QTR{q}"
        d.mkdir(parents=True)
        if q == 1:
            shutil.copy(FORM_SMALL, d / "form.idx")
        else:
            (d / "form.idx").write_text(head)
    return raw


def test_parse_form_idx_fixed_width():
    df = edgar.parse_form_idx(FORM_SMALL)
    assert df.columns == ["form", "company", "cik", "date_filed", "file_name", "adsh"]
    assert df.schema["cik"] == pl.Int64
    assert df.schema["date_filed"] == pl.Date
    assert df.height == 4
    first = df.filter(pl.col("form") == "10-K").row(0, named=True)
    assert first["company"] == "ALPHA  BETA HOLDINGS, INC."
    assert first["cik"] == 1234567
    assert first["date_filed"] == date(2024, 3, 1)
    assert first["file_name"] == "edgar/data/1234567/0001234567-24-000001.txt"
    assert first["adsh"] == "0001234567-24-000001"
    assert set(df["form"]) == {"10-K", "10-K/A", "10-KT", "8-K"}


def test_parse_form_idx_rejects_a_changed_layout(tmp_path: Path):
    lines = FORM_SMALL.read_text().split("\n")
    lines[10] = " " + lines[10][:-1]  # every column one character to the right
    bad = tmp_path / "form.idx"
    bad.write_text("\n".join(lines))
    with pytest.raises(ValueError):
        edgar.parse_form_idx(bad)


def test_ten_k_filers_excludes_amendments(tmp_path: Path):
    raw = _raw_with_year(tmp_path, 2024)
    df = edgar.ten_k_filers(2024, raw=raw)
    assert set(df["form"]) == {"10-K", "10-KT"}
    assert edgar.FORMS == ("10-K", "10-K405", "10-KT")
    assert edgar.YEARS == tuple(range(2019, 2026))


def test_ten_k_filers_refuses_a_missing_quarter(tmp_path: Path):
    raw = _raw_with_year(tmp_path, 2024)
    (raw / "sec/full-index/2024/QTR3/form.idx").unlink()
    with pytest.raises(FileNotFoundError):
        edgar.ten_k_filers(2024, raw=raw)


def test_sic_from_bulk_zip(submissions_zip: Path):
    with zipfile.ZipFile(submissions_zip) as zf:
        assert edgar.sic_of(edgar.submissions_json(1234567, zf)) == 7372
        assert edgar.sic_of(edgar.submissions_json(3333333, zf)) is None  # "" -> None
        assert edgar.submissions_json(4444444, zf) is None  # no member
        assert edgar.sic_of(edgar.submissions_json(4444444, zf)) is None
    assert edgar.sic_of({"cik": "1"}) is None  # key absent
    assert edgar.ff49_of(7372, LOOKUP) == 36
    assert edgar.ff49_of(None, LOOKUP) is None


def test_unmapped_sic_reported(tmp_path: Path, submissions_zip: Path):
    filers = pl.DataFrame(
        {
            "year": [2024, 2024, 2024],
            "cik": [1234567, 5555555, 3333333],
            "adsh": ["a", "b", "c"],
            "form": ["10-K", "10-K", "10-K"],
            "date_filed": [date(2024, 3, 1)] * 3,
            "sic": [7372, 9999, None],
        },
        schema_overrides={"sic": pl.Int64},
    ).with_columns(
        pl.col("sic")
        .map_elements(lambda s: edgar.ff49_of(s, LOOKUP), return_dtype=pl.Int64)
        .alias("ff49")
    )
    assert edgar.ff49_of(9999, LOOKUP) is None
    den = edgar.denominator(filers)
    assert den.columns == ["year", "ff49", "n_filers"]
    assert den.filter(pl.col("ff49").is_null())["n_filers"].to_list() == [2]
    assert den.filter(pl.col("ff49") == 36)["n_filers"].to_list() == [1]
    rep = edgar.unmapped_report(filers)
    row = rep.row(0, named=True)
    assert (row["n_filers"], row["n_unmapped"], row["n_no_sic"], row["n_sic_outside"]) == (
        3,
        2,
        1,
        1,
    )


def test_denominator_counts_distinct_ciks():
    filers = pl.DataFrame(
        {
            "year": [2024, 2024, 2024, 2023],
            "cik": [1, 1, 2, 1],
            "adsh": ["a", "b", "c", "d"],
            "form": ["10-K", "10-KT", "10-K", "10-K"],
            "date_filed": [date(2024, 1, 2), date(2024, 9, 1), date(2024, 5, 1), date(2023, 5, 1)],
            "sic": [7372, 7372, 7371, 7372],
            "ff49": [36, 36, 36, 36],
        }
    )
    den = edgar.denominator(filers)
    assert den.filter(pl.col("ff49") == 36).rows() == [(2023, 36, 1), (2024, 36, 2)]


def test_denominator_has_every_industry_and_the_null_row():
    filers = pl.DataFrame(
        {
            "year": [2024, 2024],
            "cik": [1, 2],
            "adsh": ["a", "b"],
            "form": ["10-K", "10-K"],
            "date_filed": [date(2024, 1, 2), date(2024, 5, 1)],
            "sic": [7372, 7371],
            "ff49": [36, 36],
        }
    )
    den = edgar.denominator(filers)
    assert den.height == 50
    assert den["ff49"].to_list() == [*range(1, 50), None]
    assert den["n_filers"].sum() == 2
    assert den.filter(pl.col("ff49") == 1)["n_filers"].to_list() == [0]
    assert den.filter(pl.col("ff49").is_null())["n_filers"].to_list() == [0]
    assert den.schema["n_filers"] == pl.Int64


@pytest.mark.data
def test_real_siccodes49_asset_backed_unmapped():
    assert edgar.ff49_of(6189) is None  # asset-backed securities: in no Siccodes49 range
    assert edgar.ff49_of(6199) == 45


def test_build_filers_end_to_end(tmp_path: Path, submissions_zip: Path):
    raw = _raw_with_year(tmp_path, 2024)
    out = tmp_path / "filers.parquet"
    df = edgar.build_filers([2024], raw=raw, zip_path=submissions_zip, lookup=LOOKUP, out=out)
    assert df.columns == ["year", "cik", "adsh", "form", "date_filed", "sic", "ff49"]
    assert out.exists() and pl.read_parquet(out).equals(df)
    got = {r["cik"]: (r["sic"], r["ff49"]) for r in df.iter_rows(named=True)}
    assert got == {1234567: (7372, 36), 3333333: (None, None)}
    with zipfile.ZipFile(submissions_zip) as zf:
        assert edgar.missing_from_zip(df["cik"], zf) == []
        assert edgar.missing_from_zip([4444444], zf) == [4444444]


def test_fetch_download_takes_src_and_path_by_keyword(tmp_path: Path, monkeypatch):
    from aideleg.acquire import fetch

    calls = []
    monkeypatch.setattr(fetch, "_download", lambda src, part: calls.append((src, part)))
    src = fetch.Source("k", "https://www.sec.gov/x", "sec/x")
    assert fetch.download(src=src, path=tmp_path / "x") is None
    assert calls == [(src, tmp_path / "x")]
