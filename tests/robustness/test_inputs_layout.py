"""Layout checks of the post-freeze robustness inputs (Plan 4 Task 3, D20).

They read the raw files only to confirm their shape; no result is computed here.
"""

from pathlib import Path

import pandas as pd
import polars as pl
import pytest

from aideleg.acquire.sources import by_key
from aideleg.config import RAW

pytestmark = pytest.mark.data


def _raw(key: str) -> Path:
    path = RAW / by_key(key).dest
    if not path.exists():
        pytest.skip(f"needs data/raw ({key}); run `uv run python -m aideleg.acquire`")
    return path


def _member(key: str, suffixes: tuple[str, ...]) -> Path:
    folder = _raw(key).with_suffix("")
    found = [p for p in folder.rglob("*") if p.suffix.lower() in suffixes]
    assert len(found) == 1, (key, found)
    return found[0]


def test_bls_crosswalk_columns():
    raw = pd.read_excel(_raw("bls_soc_2010_2018"), header=None, dtype=str)
    title_rows = next(
        i for i, row in raw.iterrows() if "2010 SOC Code" in [str(c).strip() for c in row]
    )
    df = pd.read_excel(_raw("bls_soc_2010_2018"), skiprows=title_rows, dtype=str)
    header = [str(c).strip() for c in df.columns]
    assert "2010 SOC Code" in header
    assert "2018 SOC Code" in header
    assert df["2018 SOC Code"].notna().sum() > 800


def test_work_context_has_consequence_of_error():
    df = pl.read_csv(
        _raw("onet_29_3_work_context"), separator="\t", infer_schema_length=0, quote_char=None
    )
    hits = df.filter(
        (pl.col("Element Name") == "Consequence of Error") & (pl.col("Scale ID") == "CX")
    )
    assert hits["O*NET-SOC Code"].n_unique() >= 800


def test_oews_2023_files():
    from aideleg.bls.oews import load_industry_matrix, load_national

    _raw("oews_2023_nat")
    _raw("oews_2023_ind")
    nat = load_national(2023)
    assert nat.height > 700
    assert nat["soc6"].is_unique().all()
    ind = load_industry_matrix(2023, 4)
    sums = (
        ind.filter(pl.col("emp_share_in_industry").is_not_null())
        .group_by("naics")
        .agg(s=pl.col("emp_share_in_industry").sum())
    )
    assert sums.height > 200
    assert ((sums["s"] - 1.0).abs() < 1e-9).all()


@pytest.mark.parametrize("n", [30, 48])
def test_ff30_ff48_columns_match_siccodes(n):
    from aideleg.market.french import read_french_table, read_siccodes

    daily = _member(f"ff{n}_daily", (".csv", ".txt"))
    vw = read_french_table(daily, "Average Value Weighted Returns -- Daily")
    sic = read_siccodes(_member(f"ff_siccodes{n}", (".txt",)))
    names = sic.unique("ff49", maintain_order=True).sort("ff49")["ff49_short"].to_list()
    assert len(names) == n
    assert [c for c in vw.columns if c != "date"] == names
