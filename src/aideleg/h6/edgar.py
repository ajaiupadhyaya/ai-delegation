"""H6 denominator (PAP §6, D18): 10-K filers per FF49 industry and filing year.

Filings. Form types `FORMS` (amendments such as `10-K/A`, `10-K405/A`, `10-KT/A` excluded;
the form type must equal one of them exactly), filed in calendar years `YEARS`, from the
EDGAR full index `full-index/{y}/QTR{1-4}/form.idx`. `year` is the calendar year of the index's
`Date Filed`, which is also the year of the index folder (checked). A filing listed under
several CIKs (co-registrants) is one row per CIK, as the index lists it.

SIC. The current SIC of each CIK in the bulk submissions file `submissions.zip` (C-40), member
`CIK{cik:010d}.json` (the `-submissions-NNN.json` members page older filings and carry no SIC).
A CIK with no member, or a member whose `sic` is absent or empty, has no SIC. FF49 is
`naics_ff49.sic_to_ff49` over the `Siccodes49` ranges; no SIC, or a SIC outside every range,
is unmapped: `ff49` null, counted and reported, never forced into an industry.

The denominator counts distinct CIKs per (year, FF49). Since SIC is per CIK, a CIK with several
10-Ks in a year counts once in that year.

Layout of `form.idx` (checked on every 2019-2025 quarter, 2026-10-22). Four text lines, four
blank lines, the header line, a dashed line, then fixed-width rows. The data columns do NOT
start at the header labels' offsets: the header puts `Company Name`, `CIK`, `Date Filed` and
`File Name` at 12, 74, 86 and 98, the rows at 17, 79, 91 and 103 (`Form Type` is at 0 in
both). The parser uses the row offsets, checks the header text, and refuses a row whose
fields do not sit in those columns.

Pure functions over saved files; no network.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable, Iterable, Sequence
from datetime import date
from functools import cache
from pathlib import Path

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import DERIVED, RAW

FORMS: tuple[str, ...] = ("10-K", "10-K405", "10-KT")
YEARS: tuple[int, ...] = tuple(range(2019, 2026))
FF49_INDUSTRIES: tuple[int, ...] = tuple(range(1, 50))  # Siccodes49 numbers its industries 1..49
FILERS = DERIVED / "h6/filers.parquet"

HEADER = (
    "Form Type   Company Name                                                  "
    "CIK         Date Filed  File Name"
)
# Row column starts: form, company, cik, date_filed, file_name (see the module docstring).
COLUMNS = (0, 17, 79, 91, 103)
_FILERS_SCHEMA = {
    "year": pl.Int64,
    "cik": pl.Int64,
    "adsh": pl.String,
    "form": pl.String,
    "date_filed": pl.Date,
    "sic": pl.Int64,
    "ff49": pl.Int64,
}


def _field(line: str, i: int) -> str:
    lo = COLUMNS[i]
    hi = COLUMNS[i + 1] if i + 1 < len(COLUMNS) else len(line)
    # every field is left-aligned at its column: a blank before it and a character at it
    if lo and (line[lo - 1 : lo] != " " or line[lo : lo + 1] in ("", " ")):
        raise ValueError(f"form.idx row does not fit the column layout: {line!r}")
    return line[lo:hi].strip()


def parse_form_idx(path: Path) -> pl.DataFrame:
    """One row per index line: form, company, cik (Int64), date_filed (Date), file_name, adsh."""
    lines = Path(path).read_text(encoding="latin-1").splitlines()
    try:
        h = next(i for i, ln in enumerate(lines) if ln.startswith("Form Type"))
    except StopIteration:
        raise ValueError(f"{path}: no header line") from None
    if lines[h].rstrip() != HEADER:
        raise ValueError(f"{path}: header changed: {lines[h]!r}")
    if h + 1 >= len(lines) or set(lines[h + 1].strip()) != {"-"}:
        raise ValueError(f"{path}: no dashed line after the header")
    rows = []
    for ln in lines[h + 2 :]:
        if not ln.strip():
            continue
        form, company, cik, filed, file_name = (_field(ln, i) for i in range(len(COLUMNS)))
        if not cik.isdigit() or not file_name.startswith("edgar/data/") or " " in file_name:
            raise ValueError(f"{path}: malformed row {ln!r}")
        name = file_name.rsplit("/", 1)[-1]
        if not name.endswith(".txt"):
            raise ValueError(f"{path}: file name is not a .txt: {ln!r}")
        rows.append(
            (form, company, int(cik), date.fromisoformat(filed), file_name, name[: -len(".txt")])
        )
    return pl.DataFrame(
        rows,
        schema={
            "form": pl.String,
            "company": pl.String,
            "cik": pl.Int64,
            "date_filed": pl.Date,
            "file_name": pl.String,
            "adsh": pl.String,
        },
        orient="row",
    )


def _form_idx_path(year: int, q: int, raw: Path) -> Path:
    return Path(raw) / by_key(f"sec_formidx_{year}q{q}").dest


def ten_k_filers(year: int, raw: Path = RAW) -> pl.DataFrame:
    """The FORMS rows of that year's four quarterly indexes (every quarter must be present)."""
    parts = []
    for q in range(1, 5):
        path = _form_idx_path(year, q, raw)
        if not path.exists():
            raise FileNotFoundError(f"{path}: missing; run the acquisition first")
        parts.append(parse_form_idx(path).filter(pl.col("form").is_in(FORMS)))
    df = pl.concat(parts)
    wrong = df.filter(pl.col("date_filed").dt.year() != year)
    if wrong.height:
        raise ValueError(f"{year}: {wrong.height} rows filed in another year")
    return df


def submissions_json(cik: int, zf: zipfile.ZipFile) -> dict | None:
    """The bulk submissions record of `cik`, or None if the zip has no member for it."""
    try:
        with zf.open(f"CIK{int(cik):010d}.json") as f:
            return json.load(f)
    except KeyError:
        return None


def sic_of(js: dict | None) -> int | None:
    if js is None:
        return None
    sic = js.get("sic")
    if sic is None or str(sic).strip() == "":
        return None
    return int(sic)


@cache
def _default_lookup() -> Callable[[int], int | None]:
    from aideleg.crosswalk.naics_ff49 import _siccodes, sic_to_ff49

    return sic_to_ff49(_siccodes())


def ff49_of(sic: int | None, lookup: Callable[[int], int | None] | None = None) -> int | None:
    if sic is None:
        return None
    return (lookup or _default_lookup())(sic)


def missing_from_zip(ciks: Iterable[int], zf: zipfile.ZipFile) -> list[int]:
    """The CIKs (sorted, distinct) with no `CIK{cik:010d}.json` member."""
    names = set(zf.namelist())
    return sorted({int(c) for c in ciks if f"CIK{int(c):010d}.json" not in names})


def build_filers(
    years: Sequence[int] = YEARS,
    *,
    raw: Path = RAW,
    zip_path: Path | None = None,
    lookup: Callable[[int], int | None] | None = None,
    out: Path | None = FILERS,
) -> pl.DataFrame:
    """Every D18 filing of `years` with its CIK's SIC and FF49; written to `out`."""
    zip_path = zip_path or Path(raw) / by_key("sec_submissions_bulk").dest
    filings = pl.concat(
        [ten_k_filers(y, raw).with_columns(pl.lit(y, pl.Int64).alias("year")) for y in years]
    )
    sics: dict[int, int | None] = {}
    with zipfile.ZipFile(zip_path) as zf:
        for cik in sorted(set(filings["cik"].to_list())):
            sics[cik] = sic_of(submissions_json(cik, zf))
    sic_df = pl.DataFrame(
        {
            "cik": list(sics),
            "sic": list(sics.values()),
            "ff49": [ff49_of(s, lookup) for s in sics.values()],
        },
        schema={"cik": pl.Int64, "sic": pl.Int64, "ff49": pl.Int64},
    )
    df = (
        filings.join(sic_df, on="cik", how="left")
        .select(list(_FILERS_SCHEMA))
        .cast(_FILERS_SCHEMA)
        .sort("year", "cik", "date_filed", "adsh")
    )
    if out is not None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        df.write_parquet(out)
    return df


def denominator(filers: pl.DataFrame) -> pl.DataFrame:
    """Distinct CIKs per (year, ff49): every FF49 industry 1..49 of every year present, with
    n_filers = 0 where it has no filer, then the `ff49 = null` row of the unmapped CIKs (also
    present when it is 0)."""
    counts = filers.group_by("year", "ff49").agg(
        pl.col("cik").n_unique().cast(pl.Int64).alias("n_filers")
    )
    years = filers.select(pl.col("year").cast(pl.Int64)).unique()
    cells = years.join(
        pl.DataFrame({"ff49": [*FF49_INDUSTRIES, None]}, schema={"ff49": pl.Int64}), how="cross"
    )
    return (
        cells.join(counts, on=["year", "ff49"], how="left", nulls_equal=True)
        .with_columns(pl.col("n_filers").fill_null(0))
        .select("year", "ff49", "n_filers")
        .sort("year", "ff49", nulls_last=True)
    )


def unmapped_report(filers: pl.DataFrame) -> pl.DataFrame:
    """Per year: distinct filers, unmapped ones, split into no SIC and SIC outside every range."""
    per_cik = filers.select("year", "cik", "sic", "ff49").unique()
    return (
        per_cik.group_by("year")
        .agg(
            pl.len().cast(pl.Int64).alias("n_filers"),
            pl.col("ff49").is_null().sum().cast(pl.Int64).alias("n_unmapped"),
            pl.col("sic").is_null().sum().cast(pl.Int64).alias("n_no_sic"),
            (pl.col("sic").is_not_null() & pl.col("ff49").is_null())
            .sum()
            .cast(pl.Int64)
            .alias("n_sic_outside"),
        )
        .sort("year")
    )
