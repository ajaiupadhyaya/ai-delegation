"""OEWS (Occupational Employment and Wage Statistics) loaders, May vintage.

OEWS counts employment and wages by occupation; here it supplies the labour-market weights
that AEI conversations (matched to O*NET tasks) are joined to. Nothing here says anything
about what AEI usage means for jobs.

Suppression. BLS prints `**` (estimate not available), `*` (wage not available) and `#`
(wage at or above the top-coded limit) in the numeric columns. All become null, never zero.

Ownership. The national cross-industry file holds `OWN_CODE == 1235` (all ownerships). The
industry files named `nat3d` / `nat4d` are the "cross-ownership" files: each NAICS appears
once, with the ownership scope that industry has (`5` private for most; `1`/`2`/`3` for
federal/state/local government industries; `235` for schools and hospitals; `57`, `123`).
So "cross-ownership rows only" means: read those files and never the `*_owner_*` files, and
`load_industry_matrix` raises if any NAICS shows more than one ownership code.

Occupation codes. OEWS publishes some aggregate codes ending in `0` (e.g. `15-1250`) and a
few non-standard "hybrid" detailed codes that merge SOC 2018 detailed occupations (e.g.
`25-9046`). `oews_code_for` resolves a SOC 2018 code to the OEWS code that holds it.
"""

from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW
from aideleg.occupations import soc_rollup

SUPPRESSED = ("**", "*", "#")
# OEWS prints `#` where the annual median is at or above this limit (PAP section 4.1).
A_MEDIAN_TOPCODE: dict[int, float] = {2024: 239_200.0}


def _unzipped(key: str, filename: str, raw: Path = RAW) -> Path:
    folder = (raw / by_key(key).dest).with_suffix("")
    hits = sorted(folder.rglob(filename))
    if not hits:
        raise FileNotFoundError(f"{filename} not under {folder}; run `make data`")
    return hits[0]


def _read(path: Path) -> pl.DataFrame:
    """The first sheet of an OEWS xlsx, every column as a string, suppression codes null."""
    df = pd.read_excel(path, dtype=str, engine="openpyxl", keep_default_na=False)
    out = pl.from_pandas(df).with_columns(pl.all().str.strip_chars())
    return out.with_columns(
        pl.when(pl.col(c).is_in(SUPPRESSED) | (pl.col(c) == "")).then(None)
        .otherwise(pl.col(c)).alias(c)
        for c in ("TOT_EMP", "A_MEDIAN") if c in out.columns
    )


def _num(col: str, dtype: pl.DataType) -> pl.Expr:
    return pl.col(col).cast(pl.Float64, strict=True).cast(dtype)


def load_national(year: int = 2024, *, path: Path | None = None) -> pl.DataFrame:
    """Detailed occupations, cross-industry, all ownerships: `soc6, title, tot_emp, a_median`.

    `tot_emp` (jobs, Int64) and `a_median` (annual median wage, Float64) are null where BLS
    suppresses them.
    """
    path = path or _unzipped(f"oews_{year}_nat", f"national_M{year}_dl.xlsx")
    df = _read(path).filter(pl.col("O_GROUP") == "detailed")
    return df.select(
        soc6=pl.col("OCC_CODE"), title=pl.col("OCC_TITLE"),
        tot_emp=_num("TOT_EMP", pl.Int64()), a_median=_num("A_MEDIAN", pl.Float64()),
    ).sort("soc6")


def load_national_wages(year: int = 2024, *, path: Path | None = None) -> pl.DataFrame:
    """Detailed occupations, cross-industry: `soc6, tot_emp, a_median, a_median_status`.

    For the wage regressors only; `load_national` (which nulls `#`) stays as it is, so the
    exposure inputs do not move. Reads the raw `A_MEDIAN` strings: `#` becomes the year's
    top-code (`"topcoded"`, KeyError if the year has none), `*`, `**` or empty becomes null
    (`"suppressed"`), anything else is the published number.
    """
    topcode = A_MEDIAN_TOPCODE[year]
    path = path or _unzipped(f"oews_{year}_nat", f"national_M{year}_dl.xlsx")
    raw = pd.read_excel(path, dtype=str, engine="openpyxl", keep_default_na=False)
    df = pl.from_pandas(raw).with_columns(pl.all().str.strip_chars())
    df = df.filter(pl.col("O_GROUP") == "detailed")
    med = pl.col("A_MEDIAN")
    status = (pl.when(med == "#").then(pl.lit("topcoded"))
              .when(med.is_in(["*", "**", ""])).then(pl.lit("suppressed"))
              .otherwise(pl.lit("published")))
    value = (pl.when(status == "topcoded").then(pl.lit(topcode))
             .when(status == "published").then(med.cast(pl.Float64, strict=True)))
    emp = pl.when(pl.col("TOT_EMP").is_in(SUPPRESSED) | (pl.col("TOT_EMP") == "")).then(None) \
        .otherwise(pl.col("TOT_EMP")).cast(pl.Float64, strict=True).cast(pl.Int64())
    return df.select(soc6=pl.col("OCC_CODE"), tot_emp=emp, a_median=value.cast(pl.Float64),
                     a_median_status=status).sort("soc6")


def load_industry_matrix(year: int = 2024, digits: Literal[3, 4] = 4, *,
                         path: Path | None = None) -> pl.DataFrame:
    """Industry x detailed-occupation employment: `naics, naics_title, soc6, tot_emp,
    emp_share_in_industry`.

    Cross-ownership rows only (see the module docstring). `emp_share_in_industry` is
    `tot_emp` over the industry's summed non-null detailed employment, so it sums to 1 within
    an industry; it is null where `tot_emp` is null, and for every row of an industry whose
    detailed employment is all suppressed.
    """
    if digits not in (3, 4):
        raise ValueError(f"digits must be 3 or 4, not {digits!r}")
    path = path or _unzipped(f"oews_{year}_ind", f"nat{digits}d_M{year}_dl.xlsx")
    df = _read(path)
    n_own = df.group_by("NAICS").agg(n=pl.col("OWN_CODE").n_unique()).filter(pl.col("n") > 1)
    if not n_own.is_empty():
        raise ValueError(f"more than one ownership code in NAICS {n_own['NAICS'].to_list()[:5]}"
                         f" of {path.name}: not a cross-ownership file")
    out = df.filter(pl.col("O_GROUP") == "detailed").select(
        naics=pl.col("NAICS"), naics_title=pl.col("NAICS_TITLE"), soc6=pl.col("OCC_CODE"),
        tot_emp=_num("TOT_EMP", pl.Int64()),
    )
    total = pl.col("tot_emp").sum().over("naics")
    return out.with_columns(
        emp_share_in_industry=pl.when(total > 0).then(pl.col("tot_emp") / total)
    ).sort("naics", "soc6")


def oews_code_for(soc6: str, oews_codes: set[str],
                  soc_structure: pl.DataFrame | None = None) -> str | None:
    """The OEWS code that holds the SOC 2018 detailed code `soc6`, or None.

    1. `soc6` itself, if OEWS publishes it.
    2. Its OEWS aggregate (`soc_rollup`: the broad-group code ending in `0`).
    3. An OEWS "hybrid": an OEWS code in the same SOC broad group (`soc6[:6]`, e.g. `25-904`)
       that is not a SOC 2018 detailed code (not in the structure's `Detailed Occupation`
       column). Used only when exactly one such code exists. Skipped without `soc_structure`.
    """
    if soc6 in oews_codes:
        return soc6
    rolled = soc_rollup(soc6, oews_codes)
    if rolled in oews_codes:
        return rolled
    if soc_structure is None:
        return None
    detailed = set(soc_structure["Detailed Occupation"].drop_nulls())
    hybrids = {c for c in oews_codes if c[:6] == soc6[:6] and c not in detailed
               and not c.endswith("0")}
    return next(iter(hybrids)) if len(hybrids) == 1 else None
