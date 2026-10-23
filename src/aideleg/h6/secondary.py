"""H6 secondary talk measure (PAP §6 D18, §6.1 D12, C-41, C-48): dictionary occurrences per
10,000 words of the primary 10-K document, firm-level, then the industry mean. Exploratory.

Acquisition (`download_documents`, run only by `acquire --docs`) is the only network step. It
saves each filing's primary document once per accession number, gzip-compressed, at
`data/raw/sec/docs/{cik}/{adsh}/{doc}.gz`, and appends one line per document to
`data/raw/sec/docs/INDEX.jsonl` (`key, url, dest, retrieved_utc, bytes, sha256`; bytes and
SHA-256 of the uncompressed body). Indexed documents are never fetched again, so a run resumes.
At the end it records `sec_docs_index` (INDEX.jsonl itself) in the MANIFEST.

Everything else (`filing_rates`, `industry_secondary`, `run_secondary`) reads the saved files
only and never fetches, so `h6 all` rebuilds the outputs offline.

Defaults the PAP leaves open are fixed in PAP §11 (the Task 13 clarification).

AEI data are conversations matched to O*NET tasks; nothing here speaks to the labour market.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import re
import shutil
import time
import zipfile
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW
from aideleg.h6 import edgar
from aideleg.h6.dictionary import clean_text, count_terms
from aideleg.results.common import WORDING, check_text, generated_line, write_csv
from aideleg.rq3.report import md_table

MIN_FREE_GIB = 30
DOCS_DIR = RAW / "sec/docs"
INDEX = DOCS_DIR / "INDEX.jsonl"
ERRORS = DOCS_DIR / "ERRORS.jsonl"
INDEX_KEY = "sec_docs_index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"
DOC_PAUSE = 0.05  # seconds before each document request, on top of the 0.1 s SEC spacing
BLOCKED_PAUSE = 60.0  # seconds to wait after an access-denied answer before trying again
BLOCKED_LIMIT = 3  # consecutive denied or unavailable answers that stop the run
DISK_EVERY = 100  # documents between disk checks
SHORT_WORDS = 2_000
T_YEAR = 2024
YEARS = edgar.YEARS
LABEL = "exploratory (PAP §6, D18)"
GENERATOR = "uv run python -m aideleg.h6 secondary"
HEADING = f"# H6 secondary talk measure per 10,000 words of the 10-K primary document — {LABEL}"
FIG_BY_YEAR = "fig_h6_secondary_by_year"

HTML_TYPES = (".htm", ".html")
TEXT_TYPES = (".txt",)
# a 200 body this small that carries one of these is an SEC access/error page, never a 10-K
ERROR_BODY_MAX = 64 * 1024
ERROR_MARKERS = (
    b"request rate threshold exceeded",
    b"undeclared automated tool",
    b"your request originates",
    b"access denied",
)
# a complete document ends with its closing tag, then only whitespace and comments
# (EDGAR wraps some .htm bodies in SGML: `</html>` is then followed by `</TEXT></DOCUMENT>`)
_HTML_END = re.compile(
    rb"</html\s*>(?:\s|<!--.*?-->|</(?:text|document)\s*>)*\Z", re.IGNORECASE | re.DOTALL
)
_SGML_END = re.compile(rb"</document\s*>\s*\Z", re.IGNORECASE)
_TEXT_END = re.compile(rb"</(?:document|text)\s*>(?:\s|<!--.*?-->)*\Z", re.IGNORECASE | re.DOTALL)
TAIL_BYTES = 64 * 1024  # the end marker is looked for in the last TAIL_BYTES of the body
COMPLETE_ATTEMPTS = 3  # requests of one document before an incomplete body goes to ERRORS
STATUSES = ("ok", "no_primary_document", "pdf", "other_type", "not_downloaded", "zero_words")
RATE_COLUMNS = [
    "year",
    "cik",
    "adsh",
    "ff49",
    "n_words",
    "hits_primary",
    "hits_acronym",
    "rate_per_10k",
    "status",
]
_RATE_SCHEMA = {
    "year": pl.Int64,
    "cik": pl.Int64,
    "adsh": pl.String,
    "ff49": pl.Int64,
    "n_words": pl.Int64,
    "hits_primary": pl.Int64,
    "hits_acronym": pl.Int64,
    "rate_per_10k": pl.Float64,
    "status": pl.String,
}


class BlockedError(RuntimeError):
    """SEC keeps denying access or stays unavailable: the acquisition stops (BLOCKED)."""


# --- locating documents --------------------------------------------------------------------


def _doc_map(block: dict) -> dict[str, str]:
    return dict(
        zip(block.get("accessionNumber", []), block.get("primaryDocument", []), strict=True)
    )


def primary_documents(cik: int, zf: zipfile.ZipFile) -> dict[str, str]:
    """accession number -> primaryDocument over `filings.recent` of `CIK{cik:010d}.json`, then
    each `filings.files[].name` member (an earlier listing wins); {} without a member."""
    js = edgar.submissions_json(cik, zf)
    if js is None:
        return {}
    filings = js.get("filings") or {}
    out = _doc_map(filings.get("recent") or {})
    for f in filings.get("files") or []:
        try:
            with zf.open(f["name"]) as fh:
                page = json.load(fh)
        except KeyError:
            continue
        for k, v in _doc_map(page).items():
            out.setdefault(k, v)
    return out


def primary_document(cik: int, adsh: str, zf: zipfile.ZipFile) -> str | None:
    """The primaryDocument of accession `adsh` in CIK `cik`'s submissions; None when the
    accession is not listed or its primaryDocument is empty."""
    doc = primary_documents(cik, zf).get(adsh)
    return doc.strip() if doc and doc.strip() else None


def doc_url(cik: int, adsh: str, doc: str) -> str:
    return f"{ARCHIVES}/{int(cik)}/{adsh.replace('-', '')}/{doc}"


def doc_dest(cik: int, adsh: str, doc: str) -> str:
    """Path relative to the raw directory."""
    return f"sec/docs/{int(cik)}/{adsh}/{doc}.gz"


def doc_kind(doc: str | None) -> str:
    """The kind of a document name: "html", "text", or its skip status."""
    if doc is None:
        return "no_primary_document"
    low = doc.lower()
    if low.endswith(".pdf"):
        return "pdf"
    if low.endswith(HTML_TYPES):
        return "html"
    if low.endswith(TEXT_TYPES):
        return "text"
    return "other_type"


def resolve(filers: pl.DataFrame, zf: zipfile.ZipFile) -> pl.DataFrame:
    """One row per accession number: adsh, cik (the first of the filing's CIKs, ascending, whose
    submissions list it with a primaryDocument; else the lowest), doc (or null), kind."""
    maps: dict[int, dict[str, str]] = {}
    rows = []
    for adsh, ciks in (
        filers.group_by("adsh").agg(pl.col("cik").unique().sort()).sort("adsh").iter_rows()
    ):
        found = None
        for c in ciks:
            if c not in maps:
                maps[c] = primary_documents(c, zf)
            d = maps[c].get(adsh)
            if d and d.strip():
                found = (c, d.strip())
                break
        cik, doc = found if found else (ciks[0], None)
        rows.append((adsh, cik, doc, doc_kind(doc)))
    return pl.DataFrame(
        rows,
        schema={"adsh": pl.String, "cik": pl.Int64, "doc": pl.String, "kind": pl.String},
        orient="row",
    )


# --- disk and bodies -----------------------------------------------------------------------


def assert_disk(path: Path) -> None:
    """Raise OSError when the volume of `path` has less than MIN_FREE_GIB free."""
    p = Path(path)
    while not p.exists():
        p = p.parent
    free = shutil.disk_usage(p).free
    if free < MIN_FREE_GIB * 2**30:
        raise OSError(f"{free / 2**30:.1f} GiB free under {p}; need {MIN_FREE_GIB} GiB")


def is_error_body(body: bytes) -> bool:
    """An SEC access-denied or rate-limit page served in place of a document."""
    if len(body) > ERROR_BODY_MAX:
        return False
    low = body.lower()
    return any(m in low for m in ERROR_MARKERS)


def check_complete(body: bytes, doc: str) -> tuple[bool, str]:
    """Whether a document body is whole: an .htm/.html body must end with `</html>` (any case,
    then only whitespace, comments or the SGML closers `</TEXT>`, `</DOCUMENT>`), or else end
    with EDGAR's `</DOCUMENT>` closer (a filer's malformed HTML, accepted with the reason
    stated); a .txt body with `</document>` or `</text>`, and one
    with neither is accepted with the reason stated. (ok, note); note is "" for a plain pass."""
    tail = body[-TAIL_BYTES:]
    if doc_kind(doc) == "html":
        if _HTML_END.search(tail):
            return True, ""
        if _SGML_END.search(tail):
            return True, "no </html>, but the EDGAR </DOCUMENT> closer ends the body: accepted"
        return False, f"truncated: no </html> at the end (last bytes {tail[-60:]!r})"
    if _TEXT_END.search(tail):
        return True, ""
    return True, "plain text without </document> or </text> at the end: accepted"


def scan_incomplete(raw: Path = RAW, workers: int | None = None) -> list[dict]:
    """Offline: every INDEX document whose saved body fails `check_complete`, as
    {key, dest, bytes, reason}; plain-text acceptances are returned too, with ok True."""
    from concurrent.futures import ProcessPoolExecutor

    raw = Path(raw)
    recs = list(read_index(raw / "sec/docs/INDEX.jsonl").values())
    jobs = [(str(raw / r["dest"]), r["dest"][: -len(".gz")]) for r in recs]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        res = list(ex.map(_check_file, jobs, chunksize=64))
    return [
        {"key": r["key"], "dest": r["dest"], "bytes": r["bytes"], "ok": ok, "reason": note}
        for r, (ok, note) in zip(recs, res, strict=True)
        if not ok or note
    ]


def _check_file(args: tuple[str, str]) -> tuple[bool, str]:
    path, doc = args
    with gzip.open(path, "rb") as f:
        return check_complete(f.read(), doc)


def compact_index(index: Path) -> None:
    """Rewrite INDEX.jsonl with one line per key: the latest record, at the key's first
    position (a re-fetched document replaces its line in place)."""
    order: list[str] = []
    last: dict[str, str] = {}
    for line in Path(index).read_text().splitlines():
        if line.strip():
            k = json.loads(line)["key"]
            if k not in last:
                order.append(k)
            last[k] = line
    tmp = Path(index).with_name(Path(index).name + ".tmp")
    tmp.write_text("".join(last[k] + "\n" for k in order))
    tmp.replace(index)


def save_gzip(body: bytes, target: Path) -> None:
    """Write `body` gzip-compressed to `target` (mtime 0, so equal bodies give equal files),
    through a temporary file renamed into place."""
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    with tmp.open("wb") as raw_f, gzip.GzipFile(fileobj=raw_f, mode="wb", mtime=0) as g:
        g.write(body)
    tmp.replace(target)


def read_index(index: Path = INDEX) -> dict[str, dict]:
    """key -> INDEX record (a later line for the same key wins)."""
    out: dict[str, dict] = {}
    if Path(index).exists():
        for line in Path(index).read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                out[rec["key"]] = rec
    return out


# --- acquisition (network) -----------------------------------------------------------------


def _utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_body(url: str, part: Path) -> bytes:
    from aideleg.acquire import fetch

    src = fetch.Source(f"sec_doc/{part.name}", url, str(part))
    try:
        fetch.download(src, part)
        return part.read_bytes()
    finally:
        part.unlink(missing_ok=True)


def _denied(exc: Exception) -> bool:
    """Access denied (403), or still rate-limited or failing (429, 5xx) after `fetch`'s own
    retries: wait BLOCKED_PAUSE and ask again, BLOCKED_LIMIT times in a row at most."""
    s = str(exc)
    return "403 Client Error" in s or "HTTP 429" in s or "HTTP 5" in s


def _record_manifest(raw: Path, index: Path) -> None:
    from aideleg.acquire import fetch

    recs = read_index(index)
    manifest = fetch.load_manifest(raw)
    manifest[INDEX_KEY] = fetch.FetchRecord(
        key=INDEX_KEY,
        url=f"{ARCHIVES}/",
        dest=str(Path(index).relative_to(raw)),
        retrieved_utc=max((r["retrieved_utc"] for r in recs.values()), default=_utc()),
        bytes=Path(index).stat().st_size,
        sha256=hashlib.sha256(Path(index).read_bytes()).hexdigest(),
    )
    fetch.write_manifest(raw, manifest)


def download_documents(
    filers: pl.DataFrame,
    *,
    raw: Path = RAW,
    zip_path: Path | None = None,
    limit: int | None = None,
    refetch: set[str] | frozenset[str] = frozenset(),
    log: Callable[[str], None] = print,
) -> pl.DataFrame:
    """Network: download every filing's primary document not yet in INDEX.jsonl.

    Returns one row per accession number: adsh, cik, doc, kind, status, where status is
    "indexed" (already in the index), "downloaded", a skip ("no_primary_document", "pdf",
    "other_type") or "error" (not indexed, logged in ERRORS.jsonl; a later run retries it).
    `limit` caps the number of documents requested (the pilot). Keys in `refetch` are requested
    again although indexed, and their INDEX lines are replaced in place. A body that fails
    `check_complete` is requested again, COMPLETE_ATTEMPTS times in all, then logged in
    ERRORS.jsonl and never indexed. Raises BlockedError after
    BLOCKED_LIMIT consecutive access-denied answers and OSError below MIN_FREE_GIB."""
    raw = Path(raw)
    docs_dir = raw / "sec/docs"
    index = docs_dir / "INDEX.jsonl"
    errors = docs_dir / "ERRORS.jsonl"
    zip_path = zip_path or raw / by_key("sec_submissions_bulk").dest
    docs_dir.mkdir(parents=True, exist_ok=True)
    assert_disk(docs_dir)
    with zipfile.ZipFile(zip_path) as zf:
        plan = resolve(filers, zf)
    done = read_index(index)
    status: dict[str, str] = {}
    todo = []
    for r in plan.iter_rows(named=True):
        if r["kind"] not in ("html", "text"):
            status[r["adsh"]] = r["kind"]
        elif r["adsh"] in done and r["adsh"] not in refetch:
            status[r["adsh"]] = "indexed"
        else:
            todo.append(r)
    if limit is not None:
        todo = todo[:limit]
    skips = Counter(v for v in status.values() if v != "indexed")
    log(
        f"{plan.height} accessions: {len(done)} already indexed, {len(todo)} to request, "
        f"skipped {dict(sorted(skips.items()))}"
    )
    t0 = time.monotonic()
    n_bytes = 0
    denied = 0
    n_ok = n_err = 0
    with index.open("a") as idx_f, errors.open("a") as err_f:
        for i, r in enumerate(todo, 1):
            if i % DISK_EVERY == 0:
                assert_disk(docs_dir)
            adsh, cik, doc = r["adsh"], r["cik"], r["doc"]
            url = doc_url(cik, adsh, doc)
            dest = doc_dest(cik, adsh, doc)
            target = raw / dest
            part = target.with_name(target.name + ".part")
            target.parent.mkdir(parents=True, exist_ok=True)
            body = None
            reason = ""
            incomplete = 0
            while body is None:
                time.sleep(DOC_PAUSE)
                try:
                    got = _fetch_body(url, part)
                except Exception as exc:  # FetchError and anything below it
                    if _denied(exc):
                        got, reason = None, f"denied or unavailable: {exc}"
                    else:
                        reason = f"{type(exc).__name__}: {exc}"
                        break
                else:
                    if is_error_body(got):
                        got, reason = None, f"error body: {got[:200]!r}"
                    else:
                        denied = 0
                        ok, note = check_complete(got, doc)
                        if ok:
                            body = got
                            if note:
                                log(f"  {adsh}: {note}")
                            break
                        incomplete += 1
                        reason = note
                        log(f"  {adsh}: {note[:200]} (attempt {incomplete})")
                        if incomplete >= COMPLETE_ATTEMPTS:
                            break
                        continue
                denied += 1
                log(f"  {adsh}: {reason[:200]} ({denied} in a row)")
                if denied >= BLOCKED_LIMIT:
                    raise BlockedError(
                        f"{denied} consecutive denied or unavailable answers; last {url}: "
                        f"{reason[:300]}"
                    )
                time.sleep(BLOCKED_PAUSE)
            if body is None:
                n_err += 1
                status[adsh] = "error"
                err_f.write(json.dumps({"key": adsh, "url": url, "utc": _utc(), "reason": reason}))
                err_f.write("\n")
                err_f.flush()
                log(f"  {adsh}: not saved ({reason[:200]})")
                continue
            save_gzip(body, target)
            rec = {
                "key": adsh,
                "url": url,
                "dest": dest,
                "retrieved_utc": _utc(),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            idx_f.write(json.dumps(rec) + "\n")
            idx_f.flush()
            status[adsh] = "downloaded"
            n_ok += 1
            n_bytes += len(body)
            if i % 100 == 0 or i == len(todo):
                el = time.monotonic() - t0
                eta = el / i * (len(todo) - i)
                log(
                    f"[{i}/{len(todo)}] downloaded={n_ok} errors={n_err} "
                    f"bytes={n_bytes / 2**30:.2f} GiB elapsed={el / 3600:.2f} h "
                    f"rate={i / el:.2f}/s eta={eta / 3600:.2f} h free="
                    f"{shutil.disk_usage(docs_dir).free / 2**30:.0f} GiB"
                )
    if index.exists():
        if refetch:
            compact_index(index)
        _record_manifest(raw, index)
    out = plan.with_columns(
        pl.col("adsh").replace_strict(status, default="indexed").alias("status")
    )
    log(f"downloaded {n_ok}, errors {n_err}; status counts {dict(Counter(status.values()))}")
    return out


# --- measurement (offline) -----------------------------------------------------------------


def decode(body: bytes) -> str:
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("latin-1")


def doc_counts(body: bytes, doc: str) -> dict:
    """n_words, hits_primary, hits_acronym (gated), gated of one document body."""
    text = clean_text(decode(body), html=doc_kind(doc) == "html")
    c = count_terms(text)
    return {
        "n_words": c["n_words"],
        "hits_primary": sum(c["primary"].values()),
        "hits_acronym": sum(c["acronym"].values()),
        "gated": c["gated"],
    }


def rate_per_10k(hits_primary: int, hits_acronym: int, n_words: int) -> float | None:
    """10,000 x (primary + gated acronym hits) / n_words; None when n_words == 0."""
    if n_words == 0:
        return None
    return 10_000.0 * (hits_primary + hits_acronym) / n_words


def _count_file(args: tuple[str, str]) -> dict:
    path, doc = args
    with gzip.open(path, "rb") as f:
        return doc_counts(f.read(), doc)


def filing_rates(
    filers: pl.DataFrame,
    *,
    raw: Path = RAW,
    zip_path: Path | None = None,
    workers: int | None = None,
) -> pl.DataFrame:
    """One row per filers row (year, cik, adsh, ff49) with the counts of its accession's
    primary document and `rate_per_10k`; `status` says why a row has no rate ("ok" when it has
    one; see STATUSES). Reads the saved documents only."""
    raw = Path(raw)
    index = read_index(raw / "sec/docs/INDEX.jsonl")
    zip_path = zip_path or raw / by_key("sec_submissions_bulk").dest
    with zipfile.ZipFile(zip_path) as zf:
        plan = resolve(filers, zf)
    jobs, keys = [], []
    kinds: dict[str, str] = {}
    for r in plan.iter_rows(named=True):
        if r["kind"] not in ("html", "text"):
            kinds[r["adsh"]] = r["kind"]
        elif r["adsh"] not in index:
            kinds[r["adsh"]] = "not_downloaded"
        else:
            rec = index[r["adsh"]]
            jobs.append((str(raw / rec["dest"]), rec["dest"][: -len(".gz")]))
            keys.append(r["adsh"])
    counts: dict[str, dict] = {}
    if jobs:
        if workers == 1:
            res = map(_count_file, jobs)
        else:
            from concurrent.futures import ProcessPoolExecutor

            with ProcessPoolExecutor(max_workers=workers) as ex:
                res = list(ex.map(_count_file, jobs, chunksize=16))
        for k, c in zip(keys, res, strict=True):
            counts[k] = c
            kinds[k] = "zero_words" if c["n_words"] == 0 else "ok"
    doc_rows = [
        (
            k,
            counts.get(k, {}).get("n_words"),
            counts.get(k, {}).get("hits_primary"),
            counts.get(k, {}).get("hits_acronym"),
            (
                rate_per_10k(
                    counts[k]["hits_primary"], counts[k]["hits_acronym"], counts[k]["n_words"]
                )
                if k in counts
                else None
            ),
            kinds[k],
        )
        for k in plan["adsh"].to_list()
    ]
    per_doc = pl.DataFrame(
        doc_rows,
        schema={
            "adsh": pl.String,
            "n_words": pl.Int64,
            "hits_primary": pl.Int64,
            "hits_acronym": pl.Int64,
            "rate_per_10k": pl.Float64,
            "status": pl.String,
        },
        orient="row",
    )
    return (
        filers.select("year", "cik", "adsh", "ff49")
        .join(per_doc, on="adsh", how="left")
        .select(RATE_COLUMNS)
        .cast(_RATE_SCHEMA)
        .sort("year", "cik", "adsh")
    )


def firm_year(rates: pl.DataFrame) -> pl.DataFrame:
    """year, cik, ff49, rate (mean over the CIK's filings with a rate in that year), n_docs,
    any_primary (some document of the CIK that year has a primary-term hit)."""
    return (
        rates.filter(pl.col("rate_per_10k").is_not_null())
        .group_by("year", "cik")
        .agg(
            pl.col("ff49").first(),
            pl.col("rate_per_10k").mean().alias("rate"),
            pl.len().cast(pl.Int64).alias("n_docs"),
            (pl.col("hits_primary") > 0).any().alias("any_primary"),
            ((pl.col("hits_primary") + pl.col("hits_acronym")) > 0).any().alias("any_term"),
        )
        .sort("year", "cik")
    )


def industry_secondary(rates: pl.DataFrame) -> pl.DataFrame:
    """year, ff49, n_ciks, rate: first the mean over a CIK's filings in that year, then the
    equal-weight mean over CIKs, per (year, ff49); the unmapped CIKs form the ff49 = null row."""
    return (
        firm_year(rates)
        .group_by("year", "ff49")
        .agg(pl.len().cast(pl.Int64).alias("n_ciks"), pl.col("rate").mean().alias("rate"))
        .sort("year", "ff49", nulls_last=True)
    )


def industry_grid(rates: pl.DataFrame, names: pl.DataFrame) -> pl.DataFrame:
    """`industry_secondary` on the full grid (FF49 1..49 and null for every year), with
    ff49_short; n_ciks 0 and rate null where an industry has no CIK with a rate."""
    ind = industry_secondary(rates)
    years = rates.select(pl.col("year").cast(pl.Int64)).unique()
    cells = years.join(
        pl.DataFrame({"ff49": [*edgar.FF49_INDUSTRIES, None]}, schema={"ff49": pl.Int64}),
        how="cross",
    )
    return (
        cells.join(ind, on=["year", "ff49"], how="left", nulls_equal=True)
        .with_columns(pl.col("n_ciks").fill_null(0))
        .join(names.select("ff49", "ff49_short"), on="ff49", how="left")
        .select("year", "ff49", "ff49_short", "n_ciks", "rate")
        .sort("year", "ff49", nulls_last=True)
    )


def series_by_year(rates: pl.DataFrame, grid: pl.DataFrame) -> pl.DataFrame:
    """Per year: filings, filings with a rate, CIKs with a rate, the equal-weight mean of the
    firm-year rates over every CIK (unmapped included), the equal-weight mean of the mapped
    industry means, and the share of CIKs with a primary-term hit."""
    fy = firm_year(rates)
    a = fy.group_by("year").agg(
        pl.len().cast(pl.Int64).alias("n_ciks"),
        pl.col("rate").mean().alias("rate_firms"),
        pl.col("rate").median().alias("median_firms"),
        pl.col("any_primary").mean().alias("share_any_primary"),
    )
    b = (
        grid.filter(pl.col("ff49").is_not_null() & pl.col("rate").is_not_null())
        .group_by("year")
        .agg(
            pl.col("rate").mean().alias("rate_industries"),
            pl.len().cast(pl.Int64).alias("n_industries"),
        )
    )
    c = rates.group_by("year").agg(
        pl.len().cast(pl.Int64).alias("n_filings"),
        (pl.col("status") == "ok").sum().cast(pl.Int64).alias("n_rated"),
    )
    return c.join(a, on="year", how="left").join(b, on="year", how="left").sort("year")


def status_counts(rates: pl.DataFrame) -> pl.DataFrame:
    """Per year: filings by status, and rated filings under SHORT_WORDS words (kept)."""
    wide = {s: (pl.col("status") == s).sum().cast(pl.Int64).alias(s) for s in STATUSES}
    return (
        rates.group_by("year")
        .agg(
            pl.len().cast(pl.Int64).alias("n_filings"),
            *wide.values(),
            ((pl.col("status") == "ok") & (pl.col("n_words") < SHORT_WORDS))
            .sum()
            .cast(pl.Int64)
            .alias("short"),
        )
        .sort("year")
    )


def agreement(rates: pl.DataFrame, filers: pl.DataFrame, hits: pl.DataFrame) -> pl.DataFrame:
    """Per year, over the distinct (year, CIK) filer-years: the FTS indicator (the CIK is
    counted in `edgar.numerator` that year) against the text indicator (some primary document
    of the CIK that year with a rate has a primary-term hit). Filer-years with no rated
    document are `no_text` and stay out of the agreement share."""
    fy = filers.select("year", "cik").unique()
    fts = (
        edgar._hit_ciks(hits)
        .group_by("year", "cik")
        .agg(pl.col("exhibit").all().alias("exhibit_only"))
        .join(fy, on=["year", "cik"], how="inner")
        .with_columns(pl.lit(True).alias("fts"))
    )
    text = firm_year(rates).select("year", "cik", "any_primary", "any_term")
    df = (
        fy.join(fts, on=["year", "cik"], how="left")
        .join(text, on=["year", "cik"], how="left")
        .with_columns(pl.col("fts").fill_null(False))
    )
    has = pl.col("any_primary").is_not_null()
    out = (
        df.group_by("year")
        .agg(
            pl.len().cast(pl.Int64).alias("n_filer_years"),
            (~has).sum().cast(pl.Int64).alias("no_text"),
            (~has & pl.col("fts")).sum().cast(pl.Int64).alias("no_text_fts"),
            (has & pl.col("fts") & pl.col("any_primary")).sum().cast(pl.Int64).alias("both"),
            (has & pl.col("fts") & ~pl.col("any_primary")).sum().cast(pl.Int64).alias("fts_only"),
            (has & pl.col("fts") & ~pl.col("any_primary") & pl.col("exhibit_only"))
            .sum()
            .cast(pl.Int64)
            .alias("fts_only_exhibit"),
            (has & ~pl.col("fts") & pl.col("any_primary")).sum().cast(pl.Int64).alias("text_only"),
            (has & ~pl.col("fts") & ~pl.col("any_primary")).sum().cast(pl.Int64).alias("neither"),
            (has & (pl.col("any_term") != pl.col("any_primary")))
            .sum()
            .cast(pl.Int64)
            .alias("acronym_differs"),
        )
        .with_columns(
            (
                (pl.col("both") + pl.col("neither")) / (pl.col("n_filer_years") - pl.col("no_text"))
            ).alias("agreement")
        )
        .sort("year")
    )
    return out


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    """Spearman correlation with average ranks for ties (`talk._rank_corr`)."""
    from aideleg.h6.talk import _rank_corr

    return float(_rank_corr(np.asarray(x, float), np.asarray(y, float)))


# --- documents -----------------------------------------------------------------------------


def _f(x, fmt: str = ".3f") -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else format(x, fmt)


def _md(
    series: pl.DataFrame,
    grid: pl.DataFrame,
    table24: pl.DataFrame,
    sp: dict,
    st: pl.DataFrame,
    agr: pl.DataFrame,
    unm: pl.DataFrame,
    idx_stats: dict,
) -> str:
    s_lines = [
        "| year | filings | filings with a rate | CIKs with a rate | mean over CIKs | "
        "median over CIKs | mean over industries (industries) | share of CIKs with a primary "
        "term | unmapped CIKs with a rate (share) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in series.join(unm, on="year", how="left").iter_rows(named=True):
        s_lines.append(
            f"| {r['year']} | {r['n_filings']} | {r['n_rated']} | {r['n_ciks']} | "
            f"{_f(r['rate_firms'])} | {_f(r['median_firms'])} | {_f(r['rate_industries'])} "
            f"({r['n_industries']}) | {_f(r['share_any_primary'])} | {r['n_unmapped']} "
            f"({_f(100 * r['unmapped_share'], '.2f')}%) |"
        )
    st_lines = [
        "| year | filings | with a rate | no primaryDocument | PDF | other type | "
        "not downloaded | zero words | rated, under 2,000 words (kept) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in st.iter_rows(named=True):
        st_lines.append(
            f"| {r['year']} | {r['n_filings']} | {r['ok']} | {r['no_primary_document']} | "
            f"{r['pdf']} | {r['other_type']} | {r['not_downloaded']} | {r['zero_words']} | "
            f"{r['short']} |"
        )
    a_lines = [
        "| year | filer-years | both | FTS only | text only | neither | agreement | "
        "no rated document (of which FTS talk) |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in agr.iter_rows(named=True):
        a_lines.append(
            f"| {r['year']} | {r['n_filer_years']} | {r['both']} | {r['fts_only']} | "
            f"{r['text_only']} | {r['neither']} | {_f(r['agreement'])} | {r['no_text']} "
            f"({r['no_text_fts']}) |"
        )
    n_acr = int(agr["acronym_differs"].sum())
    n_fo = int(agr["fts_only"].sum())
    n_fo_x = int(agr["fts_only_exhibit"].sum())
    nulls24 = grid.filter(
        (pl.col("year") == T_YEAR) & pl.col("ff49").is_not_null() & pl.col("rate").is_null()
    )["ff49_short"].to_list()
    wide = (
        grid.filter(pl.col("ff49").is_not_null())
        .pivot(on="year", index=["ff49", "ff49_short"], values="rate", sort_columns=True)
        .sort("ff49")
        .drop("ff49")
        .rename({"ff49_short": "industry"})
    )
    lines = [
        HEADING,
        "",
        generated_line(GENERATOR),
        "",
        "Dictionary occurrences (primary terms and gated acronyms, PAP §6.1 D12) per 10,000 words "
        "of the primary 10-K document downloaded from EDGAR, firm-level, then the industry mean "
        "(PAP §6 D18, C-41). It measures what filings say, not what firms do. Descriptive only: "
        "no interval and no test is attached to it here.",
        "",
        "## Definitions",
        "",
        "- Filings: every D18 filing 2019–2025 (`filers.parquet`, C-41, C-49), one primary "
        "document per accession number; a co-registrant filing gives the same document to each "
        "of its CIKs.",
        "- Text: HTML documents (inline XBRL included) through `clean_text` (C-48); plain-text "
        "documents through `clean_text(html=False)`. Matching: `count_terms` (D12, C-48).",
        "- Filing rate = 10,000 × (primary hits + gated acronym hits) / words. A filing with "
        "zero words, no primary document, a PDF or another type, or no saved document has no "
        "rate and is left out (counted below); filings under 2,000 words are kept.",
        "- Firm-year rate: the mean over the CIK's filings with a rate in the year. Industry "
        "rate: the equal-weight mean over the CIKs of the FF49 industry with a firm-year rate. "
        "Unmapped CIKs (no SIC, or a SIC outside Siccodes49) enter no industry.",
        "- Defaults the PAP leaves open are fixed in PAP §11 (the Task 13 clarification).",
        "",
        "## Documents",
        "",
        f"- `INDEX.jsonl`: {idx_stats['count']} documents, {idx_stats['bytes']:,} bytes "
        f"uncompressed, retrieved (UTC) {idx_stats['first']} → {idx_stats['last']}.",
        "",
        "## Series by year",
        "",
        "Rates are occurrences per 10,000 words. Mean over industries: equal-weight over the "
        "FF49 industries with a rate.",
        "",
        *s_lines,
        "",
        "## Filings without a rate, and short filings",
        "",
        *st_lines,
        "",
        f"## {T_YEAR}: secondary measure and T_j",
        "",
        f"Spearman(secondary {T_YEAR}, T_j) = {sp['rho']:.3f} over {sp['n']} FF49 industries "
        "with both defined (average ranks for ties). Descriptive: no interval and no p-value "
        "(Task 13 brief). T_j is the FTS talk share of `talk_index.md`. Industries with no "
        f"{T_YEAR} rate: {', '.join(nulls24) or 'none'}.",
        "",
        md_table(table24),
        "",
        "## Agreement between the FTS talk indicator and the text indicator",
        "",
        "Reporting only (a check on the 2023→2024 change in FTS talk). Per filer-year (distinct "
        "CIK and year of `filers.parquet`): FTS = the CIK is counted in the talk numerator "
        "that year (at least one full-text-search hit in a 10-K, 10-K405 or 10-KT filed that "
        "year, any document of the filing, C-50); text = at least one primary-term hit in a "
        "primary document of the CIK that year with a rate. Agreement = (both + neither) / the "
        "filer-years with a rated document. Gated acronyms need a gate term, itself a primary "
        f"term, so counting them changes the text indicator in {n_acr} filer-years. Both "
        "indicators look for the same primary phrases in the same filings, and the text "
        "indicator reads the primary document that FTS also searches, so an agreement near 1 "
        "is a replication check of the FTS numerator, not two constructs converging. Of the "
        f"{n_fo} FTS-only filer-years, {n_fo_x} are CIKs whose every hit that year is in an "
        "exhibit (C-39), which the primary document does not contain.",
        "",
        *a_lines,
        "",
        "## Secondary measure by industry and year",
        "",
        "Industry rate per 10,000 words (— where no CIK has a rate). CIK counts are in "
        "`secondary_talk.csv`, full precision, with the unmapped row.",
        "",
        md_table(wide),
        "",
        WORDING,
        "",
    ]
    return "\n".join(lines)


def _fig_by_year(grid: pl.DataFrame, series: pl.DataFrame):
    import matplotlib.pyplot as plt

    from aideleg.figures import FIGSIZE, PALETTE, apply_style

    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["double"])
    ind = grid.filter(pl.col("ff49").is_not_null())
    for name in sorted(set(ind["ff49_short"].to_list())):
        s = ind.filter((pl.col("ff49_short") == name) & pl.col("rate").is_not_null()).sort("year")
        ax.plot(s["year"].to_list(), s["rate"].to_list(), color="#bbbbbb", lw=0.5)
    ax.plot(
        series["year"].to_list(),
        series["rate_firms"].to_list(),
        color=PALETTE[0],
        lw=1.6,
        marker="o",
        ms=3,
        label="mean over all CIKs",
    )
    ax.plot([], [], color="#bbbbbb", lw=0.5, label="one FF49 industry")
    ax.set_xlabel("filing year")
    ax.set_ylabel("AI-term occurrences per 10,000 words")
    ax.set_title("H6 secondary talk measure by filing year (exploratory)")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def index_stats(index: Path = INDEX) -> dict:
    recs = read_index(index)
    stamps = [r["retrieved_utc"] for r in recs.values()]
    return {
        "count": len(recs),
        "bytes": sum(int(r["bytes"]) for r in recs.values()),
        "first": min(stamps, default="—"),
        "last": max(stamps, default="—"),
    }


def run_secondary(
    out_dir: Path,
    *,
    filers: pl.DataFrame | None = None,
    hits: pl.DataFrame | None = None,
    raw: Path = RAW,
    fig_dir: Path | None = None,
    workers: int | None = None,
) -> dict:
    """Write `secondary_talk.md` and `secondary_talk.csv` to `out_dir` (and the figure to
    `fig_dir` when given), from the saved documents only."""
    from aideleg.h6 import talk

    out_dir = Path(out_dir)
    filers = pl.read_parquet(edgar.FILERS) if filers is None else filers
    hits = pl.read_parquet(edgar.FTS_HITS) if hits is None else hits
    names = talk._ff49_names()
    rates = filing_rates(filers, raw=raw, workers=workers)
    grid = industry_grid(rates, names)
    series = series_by_year(rates, grid)
    st = status_counts(rates)
    agr = agreement(rates, filers, hits)
    fy = firm_year(rates)
    unm = (
        fy.group_by("year")
        .agg(
            pl.col("ff49").is_null().sum().cast(pl.Int64).alias("n_unmapped"),
            pl.col("ff49").is_null().mean().alias("unmapped_share"),
        )
        .sort("year")
    )

    t = talk.talk_table(edgar.numerator(hits, filers), edgar.denominator(filers), names)
    T = talk.t_index(t)
    table24 = (
        grid.filter((pl.col("year") == T_YEAR) & pl.col("ff49").is_not_null())
        .join(T, on="ff49_short", how="left")
        .select(
            pl.col("ff49_short").alias("industry"),
            pl.col("n_ciks").alias(f"CIKs with a rate {T_YEAR}"),
            pl.col("rate").alias(f"secondary {T_YEAR}"),
            "T",
        )
        .sort("industry")
    )
    both = table24.drop_nulls([f"secondary {T_YEAR}", "T"])
    sp = {
        "rho": spearman(both[f"secondary {T_YEAR}"].to_numpy(), both["T"].to_numpy()),
        "n": both.height,
    }
    text = _md(series, grid, table24, sp, st, agr, unm, index_stats(raw / "sec/docs/INDEX.jsonl"))
    check_text(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(grid, out_dir / "secondary_talk.csv")
    (out_dir / "secondary_talk.md").write_text(text, encoding="utf-8")
    if fig_dir is not None:
        from aideleg.figures import save_figure

        save_figure(_fig_by_year(grid, series), FIG_BY_YEAR, out_dir=Path(fig_dir))
    return {"series": series, "spearman": sp, "agreement": agr, "status": st, "grid": grid}
