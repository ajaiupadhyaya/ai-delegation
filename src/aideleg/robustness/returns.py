"""Guarded French return sets for the market robustness rows (PAP §0.5, §8.1, §9.1).

- `load_return_set` checks the seal (`assert_unsealed`) first. For any `end` after the last
  pre-seal day it then requires the committed confirmatory record
  (`guards.require_confirmatory_committed`, which reuses Plan 3's guard), before any file is read.
- FF49 goes through the bound `load_industry_returns`; FF30/FF48 are read with
  `read_french_table` from the single CSV of their unzipped folder (files acquired after the
  freeze, PAP §11 A-entries).
- Rows dated after the frozen market end 2026-08-31 are dropped.

Values stay in percent as published.
"""

from datetime import date
from typing import Literal, get_args

import polars as pl

from aideleg import power
from aideleg.config import ROOT
from aideleg.market import french, seal
from aideleg.robustness import guards

ReturnSet = Literal["ff49_vw", "ff49_ew", "ff30_vw", "ff48_vw"]
RETURN_SETS: tuple[str, ...] = get_args(ReturnSet)
MARKET_END = date(2026, 8, 31)  # the frozen market end (PAP §9.1)
_OTHER = {"ff30_vw": "ff30_daily", "ff48_vw": "ff48_daily"}
VW_DAILY = "Average Value Weighted Returns -- Daily"


def _guard(end: date) -> None:
    seal.assert_unsealed(end)
    if end > power.END:
        guards.require_confirmatory_committed(ROOT)


def load_return_set(rs: ReturnSet, end: date) -> pl.DataFrame:
    """`date` + one column per industry (percent), rows dated <= min(end, 2026-08-31)."""
    if rs not in RETURN_SETS:
        raise ValueError(f"unknown return set {rs!r}; one of {RETURN_SETS}")
    _guard(end)
    if rs in ("ff49_vw", "ff49_ew"):
        df = french.load_industry_returns("D", "VW" if rs == "ff49_vw" else "EW", end)
    else:
        df = french.read_french_table(french._single_file(_OTHER[rs]), VW_DAILY)
    return df.filter((pl.col("date") <= end) & (pl.col("date") <= MARKET_END))


def load_factors(end: date) -> pl.DataFrame:
    """Daily FF5 + UMD factors and rf (percent) under the same guard, to min(end, 2026-08-31)."""
    _guard(end)
    df = french.load_factors("D", end)
    return df.filter(pl.col("date") <= MARKET_END)
