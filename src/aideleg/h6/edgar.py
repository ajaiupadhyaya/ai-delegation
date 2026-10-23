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

The denominator functions are pure functions over saved files (no network). The numerator
(EDGAR full-text search, below) fetches through `acquire.fetch`, one MANIFEST record per
response, and `hits_from_saved` rebuilds it offline.
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Callable, Iterable, Sequence
from datetime import date, timedelta
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


# --- numerator: EDGAR full-text search (D18) ------------------------------------------------
#
# Live layout (checked 2026-10-22 on `"computer vision"`, 2024-01, tests/fixtures/sec/
# fts_sample.json): `hits.total = {value, relation}`; each `hits.hits[]` is ONE DOCUMENT of a
# filing (`_id = "{adsh}:{file name}"`), with `_source.ciks` (zero-padded strings), `adsh`,
# `form` (the filing's form: a `10-K/A` is returned by `forms=10-K` since the server filters on
# `root_forms`), `file_type` (the document's type: `10-K`, `EX-99.1`, ...) and `file_date`. The
# server pages 100 hits (`size`) and filters `file_date` with `gte startdt, lte enddt`; `from`
# cannot reach 10,000 (FTS_CAP), so a capped range is bisected until every leaf is exact.

FTS_URL = "https://efts.sec.gov/LATEST/search-index"
FTS_PAGE = 100
FTS_CAP = 10_000
FTS_HITS = DERIVED / "h6/fts_hits.parquet"
_HITS_SCHEMA = {
    "phrase": pl.String,
    "cik": pl.Int64,
    "adsh": pl.String,
    "form": pl.String,
    "file_date": pl.Date,
    "file_type": pl.String,
    "_id": pl.String,
}
_HIT_COLUMNS = [c for c in _HITS_SCHEMA if c != "_id"]
_SORT = ["phrase", "file_date", "adsh", "file_type", "cik"]


class FtsCapError(RuntimeError):
    """A single day still reaches the FTS cap: the D18 numerator is not computable as written."""


class FtsPageError(RuntimeError):
    """The pages of a range do not add up to its exact total (the index changed mid-query)."""


def _slug(phrase: str) -> str:
    return phrase.lower().replace(" ", "_")


def fts_url(phrase: str, start: date, end: date, offset: int) -> str:
    from urllib.parse import quote, urlencode

    params = {
        "q": f'"{phrase}"',
        "dateRange": "custom",
        "startdt": start.isoformat(),
        "enddt": end.isoformat(),
        "forms": ",".join(FORMS),
        "from": offset,
    }
    return f"{FTS_URL}?{urlencode(params, quote_via=quote)}"


def fts_source(phrase: str, start: date, end: date, offset: int):
    from aideleg.acquire.fetch import Source

    slug = _slug(phrase)
    return Source(
        f"sec_fts/{start}_{end}/{slug}/{offset:05d}",
        fts_url(phrase, start, end, offset),
        f"sec/fts/{start.year}/{slug}/{start}_{end}_{offset:05d}.json",
    )


class FtsServerError(RuntimeError):
    """The server kept answering with an error body instead of search results."""


FTS_ATTEMPTS = 5
FTS_RETRY_SECONDS = 30.0
FTS_PAUSE = 0.5  # seconds before each request not yet saved: gentler than the 0.1 s SEC floor


def _usable(js) -> bool:
    """Search results that are complete: `hits` present, not timed out, no failed shard (an
    Elasticsearch partial response counts as an error body)."""
    return (
        isinstance(js, dict)
        and "hits" in js
        and not js.get("timed_out", False)
        and int((js.get("_shards") or {}).get("failed", 0) or 0) == 0
    )


def _get_json(src) -> dict:
    """Fetch `src` once (MANIFEST record per response, D18) and read the saved file.

    The server can answer HTTP 200 with an error JSON (`errorType`, no `hits`; seen
    2026-10-23, `getaddrinfo EBUSY` from its search backend), or with a partial result
    (`timed_out`, or `_shards.failed > 0`). Such a body (not `_usable`) is refetched (backoff
    FTS_RETRY_SECONDS x attempt); if it persists its file and MANIFEST record are removed, so
    no error body is ever kept or used, and FtsServerError is raised (a resumed run fetches it
    again). A request not yet saved waits FTS_PAUSE first."""
    import time

    from aideleg.acquire import fetch

    if src.key not in fetch.load_manifest(RAW):
        time.sleep(FTS_PAUSE)
    js: dict = {}
    for attempt in range(FTS_ATTEMPTS):
        if attempt:
            print(f"  error body for {src.key} ({str(js)[:80]}); retry {attempt}", flush=True)
            time.sleep(FTS_RETRY_SECONDS * attempt)
        rec = fetch.fetch(src, RAW, force=bool(attempt))
        js = json.loads((Path(RAW) / rec.dest).read_text())
        if _usable(js):
            return js
    manifest = fetch.load_manifest(RAW)
    manifest.pop(src.key, None)
    fetch.write_manifest(RAW, manifest)
    (Path(RAW) / src.dest).unlink(missing_ok=True)
    raise FtsServerError(f"{src.key}: {FTS_ATTEMPTS} error bodies, last {str(js)[:300]}")


def _total(js: dict) -> tuple[int, str]:
    t = js["hits"]["total"]
    return int(t["value"]), str(t["relation"])


def _capped(js: dict) -> bool:
    value, relation = _total(js)
    return relation != "eq" or value >= FTS_CAP


def parse_fts(js: dict, phrase: str) -> pl.DataFrame:
    """One row per (hit, CIK in `_source.ciks`), every form kept, with the document `_id`."""
    rows = []
    for h in js["hits"]["hits"]:
        s = h["_source"]
        adsh = s.get("adsh") or h["_id"].split(":", 1)[0]
        fd = date.fromisoformat(s["file_date"])
        for c in s.get("ciks") or []:
            rows.append((phrase, int(c), adsh, s["form"], fd, s["file_type"], h["_id"]))
    return pl.DataFrame(rows, schema=_HITS_SCHEMA, orient="row")


def _n_no_cik(js: dict) -> int:
    return sum(1 for h in js["hits"]["hits"] if not h["_source"].get("ciks"))


def _keep_forms(df: pl.DataFrame, phrase: str, label: str, n_no_cik: int, log) -> pl.DataFrame:
    """Distinct (document, CIK) rows with form in FORMS; the other forms are counted and logged."""
    df = df.unique(["_id", "cik"], keep="first")
    other = (
        df.filter(~pl.col("form").is_in(FORMS)).unique("_id").group_by("form").len().sort("form")
    )
    if other.height or n_no_cik:
        parts = [f"{r['form']}={r['len']}" for r in other.iter_rows(named=True)]
        if n_no_cik:
            parts.append(f"no CIK={n_no_cik}")
        log(f"  {phrase!r} {label}: not counted (documents): {', '.join(parts)}")
    return df.filter(pl.col("form").is_in(FORMS))


def _range_hits(phrase: str, start: date, end: date, log, stats: dict) -> tuple[pl.DataFrame, int]:
    """Raw rows (all forms) of [start, end] and the hits without a CIK, bisecting capped ranges."""
    first = _get_json(fts_source(phrase, start, end, 0))
    stats["requests"] += 1
    if _capped(first):
        if start == end:
            value, relation = _total(first)
            raise FtsCapError(
                f"{phrase!r} on {start}: total {value} ({relation}) reaches the cap {FTS_CAP}"
            )
        mid = start + (end - start) // 2
        stats["splits"].append((str(start), str(end)))
        a, na = _range_hits(phrase, start, mid, log, stats)
        b, nb = _range_hits(phrase, mid + timedelta(days=1), end, log, stats)
        return pl.concat([a, b]), na + nb
    value, _ = _total(first)
    pages = [first]
    for off in range(FTS_PAGE, value, FTS_PAGE):
        js = _get_json(fts_source(phrase, start, end, off))
        stats["requests"] += 1
        if _total(js) != _total(first):
            raise FtsPageError(f"{phrase!r} {start}..{end}: total changed at from={off}")
        pages.append(js)
    df = pl.concat([parse_fts(js, phrase) for js in pages])
    ids = {h["_id"] for js in pages for h in js["hits"]["hits"]}
    if len(ids) != value:
        raise FtsPageError(
            f"{phrase!r} {start}..{end}: {len(ids)} distinct documents over the pages, "
            f"total {value}"
        )
    return df, sum(_n_no_cik(js) for js in pages)


def fts_hits(phrase: str, start: date, end: date, *, log=print, stats: dict | None = None):
    """Hits of `phrase` filed in [start, end]: columns phrase, cik, adsh, form, file_date,
    file_type; one row per (document hit, CIK); form in FORMS only."""
    stats = stats if stats is not None else {}
    stats.setdefault("requests", 0)
    stats.setdefault("splits", [])
    raw, n_no_cik = _range_hits(phrase, start, end, log, stats)
    df = _keep_forms(raw, phrase, f"{start}..{end}", n_no_cik, log)
    stats["documents"] = raw["_id"].n_unique() + n_no_cik if raw.height else n_no_cik
    return df.select(_HIT_COLUMNS).sort(_SORT)


def acquire_fts(
    years: Sequence[int] = YEARS,
    phrases: Sequence[str] | None = None,
    *,
    out: Path | None = FTS_HITS,
    log=print,
) -> pl.DataFrame:
    """Network: every phrase x calendar year through `fts_hits`; written to `out`."""
    import time

    from aideleg.h6.dictionary import fts_phrases

    phrases = list(phrases) if phrases is not None else fts_phrases()
    parts = []
    t0 = time.monotonic()
    total_requests = 0
    for phrase in phrases:
        for y in years:
            st: dict = {}
            df = fts_hits(phrase, date(y, 1, 1), date(y, 12, 31), log=log, stats=st)
            total_requests += st["requests"]
            log(
                f"{phrase!r} {y}: documents={st['documents']} kept rows={df.height} "
                f"CIKs={df['cik'].n_unique()} requests={st['requests']} "
                f"splits={st['splits'] or 'none'} "
                f"[{total_requests} requests, {time.monotonic() - t0:.0f}s]"
            )
            parts.append(df)
    hits = pl.concat(parts).sort(_SORT)
    if out is not None:
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        hits.write_parquet(out)
    return hits


def _parse_fts_key(key: str) -> tuple[date, date, str, int]:
    _, rng, slug, off = key.split("/")
    s, e = rng.split("_")
    return date.fromisoformat(s), date.fromisoformat(e), slug, int(off)


def hits_from_saved(
    phrases: Sequence[str] | None = None, start: date | None = None, end: date | None = None
) -> pl.DataFrame:
    """The `fts_hits` frame rebuilt offline from the saved `sec_fts/` responses of the MANIFEST
    (leaf ranges only: an exact page 0 below the cap, with all its pages), optionally restricted
    to `phrases` and to hits with file_date in [start, end]."""
    from aideleg.acquire import fetch
    from aideleg.h6.dictionary import fts_phrases

    names = {_slug(p): p for p in fts_phrases()}
    if phrases is not None:
        names.update({_slug(p): p for p in phrases})
        wanted = {_slug(p) for p in phrases}
    manifest = fetch.load_manifest(RAW)
    ranges: dict[tuple[date, date, str], dict[int, str]] = {}
    for key, rec in manifest.items():
        if key.startswith("sec_fts/"):
            s, e, slug, off = _parse_fts_key(key)
            if phrases is None or slug in wanted:
                ranges.setdefault((s, e, slug), {})[off] = rec.dest
    parts = []
    for (s, e, slug), pages in sorted(ranges.items()):
        if 0 not in pages:
            continue  # only deeper pages of a range: never a leaf on its own
        if (start is not None and e < start) or (end is not None and s > end):
            continue  # no hit of this range can fall in [start, end]
        phrase = names.get(slug, slug.replace("_", " "))
        first = json.loads((Path(RAW) / pages[0]).read_text())
        if _capped(first):
            continue
        value, _ = _total(first)
        for off in range(0, value, FTS_PAGE):
            if off not in pages:
                raise FileNotFoundError(f"sec_fts/{s}_{e}/{slug}/{off:05d}: page not saved")
        for off in range(0, value, FTS_PAGE):
            js = first if off == 0 else json.loads((Path(RAW) / pages[off]).read_text())
            if not _usable(js):
                raise ValueError(f"sec_fts/{s}_{e}/{slug}/{off:05d}: saved body is not usable")
            parts.append(parse_fts(js, phrase))
    if not parts:
        return pl.DataFrame(schema={c: _HITS_SCHEMA[c] for c in _HIT_COLUMNS})
    df = pl.concat(parts).unique(["phrase", "_id", "cik"], keep="first")
    df = df.filter(pl.col("form").is_in(FORMS))
    if start is not None:
        df = df.filter(pl.col("file_date") >= start)
    if end is not None:
        df = df.filter(pl.col("file_date") <= end)
    return df.select(_HIT_COLUMNS).sort(_SORT)


def _hit_ciks(hits: pl.DataFrame) -> pl.DataFrame:
    """year (of file_date), cik, exhibit (the hit's document is not a FORMS document); the
    hits with form in FORMS only."""
    return hits.filter(pl.col("form").is_in(FORMS)).select(
        pl.col("file_date").dt.year().cast(pl.Int64).alias("year"),
        pl.col("cik").cast(pl.Int64),
        (~pl.col("file_type").is_in(FORMS)).alias("exhibit"),
    )


def numerator(hits: pl.DataFrame, filers: pl.DataFrame) -> pl.DataFrame:
    """Distinct hit CIKs per (year, ff49) among that year's filers (n_talk), and those whose every
    hit is in an exhibit (n_exhibit_only, C-39: also in n_talk). Same grid as `denominator`."""
    per_cik = (
        _hit_ciks(hits)
        .group_by("year", "cik")
        .agg(pl.col("exhibit").all().alias("exhibit_only"))
        .join(filers.select("year", "cik", "ff49").unique(), on=["year", "cik"], how="inner")
    )
    counts = per_cik.group_by("year", "ff49").agg(
        pl.len().cast(pl.Int64).alias("n_talk"),
        pl.col("exhibit_only").sum().cast(pl.Int64).alias("n_exhibit_only"),
    )
    return (
        denominator(filers)
        .select("year", "ff49")
        .join(counts, on=["year", "ff49"], how="left", nulls_equal=True)
        .with_columns(pl.col("n_talk", "n_exhibit_only").fill_null(0))
        .select("year", "ff49", "n_talk", "n_exhibit_only")
        .sort("year", "ff49", nulls_last=True)
    )


def out_of_denominator(hits: pl.DataFrame, filers: pl.DataFrame) -> pl.DataFrame:
    """year, cik of hit CIKs (form in FORMS) that are not that year's filers: reported only."""
    return (
        _hit_ciks(hits)
        .select("year", "cik")
        .unique()
        .join(filers.select("year", "cik").unique(), on=["year", "cik"], how="anti")
        .sort("year", "cik")
    )
