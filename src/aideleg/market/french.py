"""Readers for the Kenneth French data-library files. Values stay in percent as published."""

import calendar
import re
from datetime import date
from pathlib import Path
from typing import Literal

import polars as pl

from aideleg.acquire import sources
from aideleg.config import RAW, SEAL_DATE
from aideleg.market import seal

_MISSING = {-99.99, -999.0}
_DATE_RE = re.compile(r"^\d{6}$|^\d{8}$")


def _parse_date(s: str) -> date:
    if len(s) == 8:
        return date(int(s[:4]), int(s[4:6]), int(s[6:]))
    y, m = int(s[:4]), int(s[4:])
    return date(y, m, calendar.monthrange(y, m)[1])


def read_french_table(path: Path, title_startswith: str) -> pl.DataFrame:
    """Return one table from a stacked French file.

    A table is a title line, a header line starting with a comma, then rows whose first
    field is YYYYMMDD or YYYYMM. `title_startswith=""` selects the first untitled table
    (the factor files). The table ends at the first line that is not a dated row.
    Annual tables (YYYY dates) never match. -99.99 and -999 become null.
    Before pap-v1 the table also ends at the first row dated on or after SEAL_DATE: sealed
    rows are never parsed, not merely filtered out afterwards.
    """
    frozen = seal.pap_frozen()
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if not line.startswith(","):
            continue
        if title_startswith == "":
            header_idx = i
            break
        if i > 0 and lines[i - 1].strip().startswith(title_startswith.strip()):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError(f"table {title_startswith!r} not found in {path}")
    names = [c.strip() for c in lines[header_idx].split(",")[1:]]
    dates: list[date] = []
    cols: list[list[float | None]] = [[] for _ in names]
    for offset, line in enumerate(lines[header_idx + 1 :]):
        lineno = header_idx + 2 + offset
        parts = [p.strip() for p in line.split(",")]
        if not _DATE_RE.match(parts[0]):
            break
        if not frozen and _parse_date(parts[0]) >= SEAL_DATE:
            break
        if len(parts) != len(names) + 1:
            raise ValueError(
                f"{path}:{lineno}: expected {len(names) + 1} fields, got {len(parts)}"
            )
        dates.append(_parse_date(parts[0]))
        for j, v in enumerate(parts[1:]):
            try:
                x = float(v) if v else None
            except ValueError:
                raise ValueError(f"{path}:{lineno}: non-numeric cell {v!r}") from None
            cols[j].append(None if x in _MISSING else x)
    data: dict[str, object] = {"date": pl.Series("date", dates, dtype=pl.Date)}
    for n, c in zip(names, cols, strict=True):
        data[n] = pl.Series(n, c, dtype=pl.Float64)
    df = pl.DataFrame(data)
    if not frozen:
        # defence in depth: the reader never hands out sealed rows before pap-v1
        df = df.filter(pl.col("date") < SEAL_DATE)
    return df


def _single_file(key: str) -> Path:
    folder = RAW / Path(sources.by_key(key).dest).with_suffix("")
    candidates = folder.glob("*") if folder.is_dir() else []
    found = [p for p in candidates if p.suffix.lower() in {".csv", ".txt"}]
    if len(found) != 1:
        raise FileNotFoundError(f"expected exactly one csv/txt in {folder}, found {len(found)}")
    return found[0]


def load_industry_returns(
    freq: Literal["D", "M"], weighting: Literal["VW", "EW"], end: date
) -> pl.DataFrame:
    seal.assert_unsealed(end)
    key = "ff49_daily" if freq == "D" else "ff49_monthly"
    kind = "Value" if weighting == "VW" else "Equal"
    span = "Daily" if freq == "D" else "Monthly"
    df = read_french_table(_single_file(key), f"Average {kind} Weighted Returns -- {span}")
    return df.filter(pl.col("date") <= end)


def load_factors(freq: Literal["D", "M"], end: date) -> pl.DataFrame:
    seal.assert_unsealed(end)
    p = "daily" if freq == "D" else "monthly"
    ff5 = read_french_table(_single_file(f"ff5_{p}"), "")
    mom = read_french_table(_single_file(f"mom_{p}"), "")
    ff5 = ff5.rename({c: c.lower().replace("-", "_") for c in ff5.columns})
    mom = mom.rename({c: c.lower() for c in mom.columns}).rename({"mom": "umd"})
    df = ff5.join(mom, on="date", how="inner").sort("date")
    df = df.select("date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf", "umd")
    return df.filter(pl.col("date") <= end)


_IND_RE = re.compile(r"^\s*(\d+)\s+(\S+)\s+(.+?)\s*$")
_RANGE_RE = re.compile(r"^\s+(\d{4})-(\d{4})\b")


def read_siccodes(path: Path) -> pl.DataFrame:
    rows: list[tuple[int, str, str, int, int]] = []
    cur: tuple[int, str, str] | None = None
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if not line.strip():
            continue
        m = _RANGE_RE.match(line)
        if m:
            if cur is None:
                raise ValueError(f"SIC range before any industry in {path}")
            rows.append((*cur, int(m.group(1)), int(m.group(2))))
            continue
        m = _IND_RE.match(line)
        if m:
            cur = (int(m.group(1)), m.group(2), m.group(3))
    return pl.DataFrame(
        rows,
        schema={
            "ff49": pl.Int64,
            "ff49_short": pl.String,
            "ff49_name": pl.String,
            "sic_lo": pl.Int64,
            "sic_hi": pl.Int64,
        },
        orient="row",
    )
