"""Guarded market and exposure loaders for the Plan 3 analyses.

Every loader that reads French data calls `guard.assert_confirmatory_recorded` first. No result
is computed here. French values stay in percent as published.
"""

import re
from datetime import date
from pathlib import Path
from typing import Literal

import polars as pl

from aideleg import audit, confirm_h5, power
from aideleg.config import DERIVED
from aideleg.market import french
from aideleg.rq3 import guard

MARKET_END = date(2026, 8, 31)

# PAP section 11, C-35: the ME held in the "Average Firm Size" row dated t is the ME at month
# end t - SIZE_ME_OFFSET (verified empirically against the published files).
SIZE_ME_OFFSET = 1

_ANNUAL_RE = re.compile(r"^\d{4}$")
_MISSING = {-99.99, -999.0}
_DESIGNS = ("B", "A_r2", "A_pooled")


def daily(weighting: Literal["VW", "EW"] = "VW") -> tuple[pl.DataFrame, pl.DataFrame]:
    guard.assert_confirmatory_recorded()
    return (french.load_industry_returns("D", weighting, MARKET_END),
            french.load_factors("D", MARKET_END))


def monthly(weighting: Literal["VW", "EW"] = "VW") -> tuple[pl.DataFrame, pl.DataFrame]:
    guard.assert_confirmatory_recorded()
    return (french.load_industry_returns("M", weighting, MARKET_END),
            french.load_factors("M", MARKET_END))


def ff3_monthly() -> pl.DataFrame:
    """`date, mkt_rf, smb, hml, rf` (percent), the first monthly table, to MARKET_END."""
    guard.assert_confirmatory_recorded()
    df = french.read_french_table(french._single_file("ff3_monthly"), "")
    df = df.rename({c: c.lower().replace("-", "_") for c in df.columns})
    return df.select("date", "mkt_rf", "smb", "hml", "rf").filter(pl.col("date") <= MARKET_END)


def _read_french_annual(path: Path, title: str) -> pl.DataFrame:
    """The YYYY-dated table that follows `title`: `year` plus one Float64 column per industry."""
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if i > 0 and line.startswith(",") and lines[i - 1].strip().startswith(title.strip()):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"table {title!r} not found in {path}")
    names = [c.strip() for c in lines[header_idx].split(",")[1:]]
    years: list[int] = []
    cols: list[list[float | None]] = [[] for _ in names]
    for offset, line in enumerate(lines[header_idx + 1:]):
        lineno = header_idx + 2 + offset
        parts = [p.strip() for p in line.split(",")]
        if not _ANNUAL_RE.match(parts[0]):
            break
        if len(parts) != len(names) + 1:
            raise ValueError(f"{path}:{lineno}: expected {len(names) + 1} fields, got {len(parts)}")
        years.append(int(parts[0]))
        for j, v in enumerate(parts[1:]):
            try:
                x = float(v) if v else None
            except ValueError:
                raise ValueError(f"{path}:{lineno}: non-numeric cell {v!r}") from None
            cols[j].append(None if x in _MISSING else x)
    out: dict[str, pl.Series] = {"year": pl.Series("year", years, dtype=pl.Int64)}
    for n, c in zip(names, cols, strict=True):
        out[n] = pl.Series(n, c, dtype=pl.Float64)
    return pl.DataFrame(out)


def _monthly_file() -> Path:
    return french._single_file("ff49_monthly")


def characteristics() -> pl.DataFrame:
    """Long `date, me_date, ff49_short, n_firms, avg_size, cap`; select rows by `me_date`."""
    guard.assert_confirmatory_recorded()
    path = _monthly_file()
    firms = french.read_french_table(path, "Number of Firms in Portfolios")
    size = french.read_french_table(path, "Average Firm Size")
    names = [c for c in firms.columns if c != "date"]
    long_f = firms.unpivot(names, index="date", variable_name="ff49_short", value_name="n_firms")
    long_s = size.unpivot(names, index="date", variable_name="ff49_short", value_name="avg_size")
    df = long_f.join(long_s, on=["date", "ff49_short"], how="inner")
    df = df.filter(pl.col("date") <= MARKET_END).with_columns(
        me_date=pl.col("date").dt.offset_by(f"-{SIZE_ME_OFFSET}mo").dt.month_end(),
        cap=pl.col("n_firms") * pl.col("avg_size"))
    return df.select("date", "me_date", "ff49_short", "n_firms", "avg_size", "cap").sort(
        "ff49_short", "date")


def beme() -> pl.DataFrame:
    """Long `year, ff49_short, beme` from "Sum of BE / Sum of ME"; values <= 0 become null."""
    guard.assert_confirmatory_recorded()
    wide = _read_french_annual(_monthly_file(), "Sum of BE / Sum of ME")
    names = [c for c in wide.columns if c != "year"]
    long = wide.unpivot(names, index="year", variable_name="ff49_short", value_name="beme")
    return long.with_columns(
        pl.when(pl.col("beme") > 0).then(pl.col("beme")).otherwise(None).alias("beme")
    ).sort("ff49_short", "year")


def zero_assigned() -> pl.DataFrame:
    """Zero-assigned employment share per design. Reads no market data."""
    return audit.design_zero_assigned(pl.read_parquet(DERIVED / "exposure_occupation.parquet"))


def exposures() -> pl.DataFrame:
    """`design, ff49, ff49_short, z_delegation, z_usage, z_aioe` for B, A_r2, A_pooled.

    Refuses unless the Design B vector is the one the confirmatory run used.
    """
    expo = power.load_exposure()
    if confirm_h5._vector_hash(expo) != confirm_h5.EXPOSURE_SHA256:
        raise ValueError(
            "Design B exposure vector does not hash to confirm_h5.EXPOSURE_SHA256: the derived "
            "data differ from the committed confirmatory record")
    aioe = expo.select("ff49", "z_aioe")
    ex = pl.read_parquet(DERIVED / "exposure_ff49.parquet").filter(
        pl.col("design").is_in(_DESIGNS))
    ex = ex.select("design", "ff49", "ff49_short", "z_delegation", "z_usage").join(
        aioe, on="ff49", how="left")
    return ex.sort("design", "ff49")
