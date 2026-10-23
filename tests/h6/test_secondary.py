"""H6 secondary talk measure (PAP §6 D18, §6.1 D12, C-41, C-48): per-10k-word rates of the
primary 10-K document, firm-year mean then industry mean. Synthetic data, no network."""

import gzip
import hashlib
import json
import shutil
import zipfile
from collections import namedtuple
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg.acquire import fetch
from aideleg.h6 import secondary


def _block(pairs):
    return {"accessionNumber": [a for a, _ in pairs], "primaryDocument": [d for _, d in pairs]}


def _zip(path: Path, members: dict[str, dict]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, js in members.items():
            zf.writestr(name, json.dumps(js))
    return path


def _sub(cik: int, recent, pages=()) -> dict[str, dict]:
    files = [{"name": f"CIK{cik:010d}-submissions-{i:03d}.json"} for i in range(1, len(pages) + 1)]
    out = {
        f"CIK{cik:010d}.json": {
            "cik": str(cik),
            "filings": {"recent": _block(recent), "files": files},
        }
    }
    for f, page in zip(files, pages, strict=True):
        out[f["name"]] = _block(page)
    return out


def test_primary_document_lookup_uses_recent_then_extra_pages(tmp_path):
    zp = _zip(
        tmp_path / "s.zip",
        _sub(1, [("0000000001-24-000001", "a10k.htm")], [[("0000000001-19-000001", "old.htm")]]),
    )
    with zipfile.ZipFile(zp) as zf:
        assert secondary.primary_document(1, "0000000001-24-000001", zf) == "a10k.htm"
        assert secondary.primary_document(1, "0000000001-19-000001", zf) == "old.htm"
        assert secondary.primary_document(1, "0000000001-99-999999", zf) is None
        assert secondary.primary_document(2, "0000000001-24-000001", zf) is None


def test_doc_url_and_kinds():
    assert (
        secondary.doc_url(320193, "0000320193-24-000123", "aapl-20240928.htm")
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"
    )
    assert secondary.doc_kind("x.HTM") == "html"
    assert secondary.doc_kind("x.txt") == "text"
    assert secondary.doc_kind("x.pdf") == "pdf"
    assert secondary.doc_kind("x.xml") == "other_type"
    assert secondary.doc_kind(None) == "no_primary_document"


def test_rate_per_10k_words():
    body = ("word " * 19_996 + "artificial intelligence machine learning").encode()
    c = secondary.doc_counts(body, "x.htm")
    assert c["n_words"] == 20_000 and c["hits_primary"] == 2
    assert secondary.rate_per_10k(c["hits_primary"], c["hits_acronym"], c["n_words"]) == 1.0
    assert secondary.rate_per_10k(0, 0, 0) is None


def test_plain_text_documents_are_not_stripped_of_angle_brackets():
    body = b"<artificial intelligence> and AI here"
    html = secondary.doc_counts(body, "x.htm")
    text = secondary.doc_counts(body, "x.txt")
    assert html["hits_primary"] == 0
    assert text["hits_primary"] == 1 and text["hits_acronym"] == 1


def _rates(rows):
    return pl.DataFrame(
        rows,
        schema={
            "year": pl.Int64,
            "cik": pl.Int64,
            "ff49": pl.Int64,
            "rate_per_10k": pl.Float64,
            "hits_primary": pl.Int64,
            "hits_acronym": pl.Int64,
        },
        orient="row",
    )


def test_firm_year_mean_then_industry_mean():
    rates = _rates(
        [
            (2024, 1, 7, 1.0, 1, 0),
            (2024, 1, 7, 3.0, 1, 0),
            (2024, 2, 7, 6.0, 1, 0),
            (2024, 3, 7, None, None, None),  # skipped: no rate, not in the mean
        ]
    )
    ind = secondary.industry_secondary(rates)
    r = ind.filter(pl.col("ff49") == 7).row(0, named=True)
    assert r["rate"] == 4.0 and r["n_ciks"] == 2


def test_disk_guard_refuses_below_threshold(monkeypatch, tmp_path):
    Usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda p: Usage(100 * 2**30, 90 * 2**30, 10 * 2**30))
    with pytest.raises(OSError):
        secondary.assert_disk(tmp_path)
    monkeypatch.setattr(shutil, "disk_usage", lambda p: Usage(100 * 2**30, 50 * 2**30, 50 * 2**30))
    secondary.assert_disk(tmp_path / "not" / "yet")


def test_error_body_is_detected():
    assert secondary.is_error_body(b"<html><h1>Request Rate Threshold Exceeded</h1></html>")
    assert not secondary.is_error_body(b"<html>annual report</html>")
    assert not secondary.is_error_body(b"access denied " + b"x" * (secondary.ERROR_BODY_MAX + 1))


# --- acquisition with a fake network -------------------------------------------------------

A1, A2, A3, A4 = (f"0000000001-24-00000{i}" for i in range(1, 5))


def _filers() -> pl.DataFrame:
    rows = [
        (2024, 1, A1, 7),
        (2024, 1, A2, 7),
        (2024, 2, A3, 7),
        (2024, 2, A4, 7),
        (2024, 3, A3, None),  # co-registrant on A3: one download, both rows get its rate
    ]
    return pl.DataFrame(
        rows,
        schema={"year": pl.Int64, "cik": pl.Int64, "adsh": pl.String, "ff49": pl.Int64},
        orient="row",
    ).with_columns(pl.lit("10-K").alias("form"), pl.lit(date(2024, 3, 1)).alias("date_filed"))


BODIES = {
    "a.htm": b"<html><p>artificial intelligence</p> " + b"w " * 9_998 + b"</html>\n",
    "b.htm": b"<html><p>nothing</p> " + b"w " * 9_999 + b"</HTML> <!-- end -->\n",
    "c.txt": b"machine learning and AI with artificial intelligence " + b"w " * 9_993,
}


@pytest.fixture
def world(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    members = {}
    members.update(_sub(1, [(A1, "a.htm"), (A2, "b.htm")]))
    members.update(_sub(2, [(A3, "c.txt"), (A4, "d.pdf")]))
    zp = _zip(tmp_path / "s.zip", members)
    calls: list[str] = []

    def fake_download(src, path):
        calls.append(src.url)
        Path(path).write_bytes(BODIES[src.url.rsplit("/", 1)[-1]])

    monkeypatch.setattr(fetch, "download", fake_download)
    monkeypatch.setattr(secondary, "DOC_PAUSE", 0.0)
    return raw, zp, calls


def test_resume_skips_indexed_documents(world):
    raw, zp, calls = world
    out = secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    assert len(calls) == 3
    assert dict(zip(out["adsh"], out["status"], strict=True)) == {
        A1: "downloaded",
        A2: "downloaded",
        A3: "downloaded",
        A4: "pdf",
    }
    calls.clear()
    out = secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    assert calls == []
    assert set(out.filter(pl.col("adsh") != A4)["status"]) == {"indexed"}
    lines = (raw / "sec/docs/INDEX.jsonl").read_text().splitlines()
    assert len(lines) == 3
    man = fetch.load_manifest(raw)
    assert (
        man["sec_docs_index"].sha256
        == hashlib.sha256((raw / "sec/docs/INDEX.jsonl").read_bytes()).hexdigest()
    )


def test_gzip_hash_is_of_uncompressed_body(world):
    raw, zp, _ = world
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    recs = secondary.read_index(raw / "sec/docs/INDEX.jsonl")
    rec = recs[A1]
    assert rec["dest"] == f"sec/docs/1/{A1}/a.htm.gz"
    assert rec["url"].endswith(f"/1/{A1.replace('-', '')}/a.htm")
    with gzip.open(raw / rec["dest"], "rb") as f:
        body = f.read()
    assert body == BODIES["a.htm"]
    assert rec["bytes"] == len(body)
    assert rec["sha256"] == hashlib.sha256(body).hexdigest()
    assert rec["sha256"] != hashlib.sha256((raw / rec["dest"]).read_bytes()).hexdigest()


def test_error_bodies_are_never_kept(world, monkeypatch):
    raw, zp, calls = world
    monkeypatch.setattr(secondary, "BLOCKED_PAUSE", 0.0)
    monkeypatch.setattr(
        fetch,
        "download",
        lambda src, path: Path(path).write_bytes(
            b"<html>Your Request Originates from an Undeclared Automated Tool</html>"
        ),
    )
    with pytest.raises(secondary.BlockedError):
        secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    assert not list((raw / "sec/docs").rglob("*.gz"))
    assert secondary.read_index(raw / "sec/docs/INDEX.jsonl") == {}


def test_filing_rates_offline_with_statuses(world, monkeypatch):
    raw, zp, calls = world
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    monkeypatch.setattr(fetch, "download", lambda *a, **k: pytest.fail("network"))
    r = secondary.filing_rates(_filers(), raw=raw, zip_path=zp, workers=1)
    assert r.columns == secondary.RATE_COLUMNS
    by = {(x["cik"], x["adsh"]): x for x in r.iter_rows(named=True)}
    assert by[(1, A1)]["rate_per_10k"] == 1.0 and by[(1, A1)]["status"] == "ok"
    assert by[(1, A2)]["rate_per_10k"] == 0.0
    # c.txt: 2 primary + 1 gated acronym in 10,000 words; same document for CIKs 2 and 3
    assert by[(2, A3)]["hits_primary"] == 2 and by[(2, A3)]["hits_acronym"] == 1
    assert by[(2, A3)]["rate_per_10k"] == pytest.approx(3.0)
    assert by[(3, A3)]["rate_per_10k"] == by[(2, A3)]["rate_per_10k"]
    assert by[(2, A4)]["status"] == "pdf" and by[(2, A4)]["rate_per_10k"] is None


def test_agreement_counts_filer_years():
    rates = pl.DataFrame(
        [
            (2024, 1, "a", 7, 100, 1, 0, 1.0, "ok"),
            (2024, 2, "b", 7, 100, 0, 0, 0.0, "ok"),
            (2024, 3, "c", 7, 100, 0, 0, 0.0, "ok"),
            (2024, 4, "d", 7, None, None, None, None, "pdf"),
        ],
        schema=secondary._RATE_SCHEMA,
        orient="row",
    )
    filers = rates.select("year", "cik")
    hits = pl.DataFrame(
        {
            "phrase": ["x", "x"],
            "cik": [2, 4],
            "adsh": ["b", "d"],
            "form": ["10-K", "10-K"],
            "file_date": [date(2024, 2, 1)] * 2,
            "file_type": ["10-K", "10-K"],
        },
    )
    a = secondary.agreement(rates, filers, hits).row(0, named=True)
    assert (a["both"], a["fts_only"], a["text_only"], a["neither"]) == (0, 1, 1, 1)
    assert a["no_text"] == 1 and a["no_text_fts"] == 1
    assert a["fts_only_exhibit"] == 0
    ex = hits.with_columns(pl.lit("EX-99.1").alias("file_type"))
    assert secondary.agreement(rates, filers, ex).row(0, named=True)["fts_only_exhibit"] == 1
    assert a["agreement"] == pytest.approx(1 / 3)


def test_run_secondary_writes_labelled_docs(world, tmp_path):
    from aideleg.acquire.sources import by_key
    from aideleg.results.common import WORDING

    raw, zp, _ = world
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    dest = raw / by_key("sec_submissions_bulk").dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(zp, dest)
    hits = pl.DataFrame(
        {
            "phrase": ["x"],
            "cik": [1],
            "adsh": [A1],
            "form": ["10-K"],
            "file_date": [date(2024, 3, 1)],
            "file_type": ["10-K"],
        }
    )
    out = tmp_path / "out"
    r = secondary.run_secondary(out, filers=_filers(), hits=hits, raw=raw, workers=1)
    md = (out / "secondary_talk.md").read_text(encoding="utf-8")
    assert "exploratory (PAP §6, D18)" in md.splitlines()[0]
    assert md.count(WORDING) == 1
    assert (out / "secondary_talk.csv").exists()
    s24 = r["series"].row(0, named=True)
    assert s24["n_filings"] == 5 and s24["n_rated"] == 4
    a = r["agreement"].row(0, named=True)
    assert (a["both"], a["fts_only"], a["text_only"], a["neither"]) == (1, 0, 2, 0)


def test_completeness_needs_the_end_marker():
    assert secondary.check_complete(b"<html><body>x</body></html>\n", "a.htm") == (True, "")
    assert secondary.check_complete(b"<html>x</HTML>\n<!-- c -->\r\n", "a.htm")[0]
    assert secondary.check_complete(b"<html>x</html>\n</TEXT>\n</DOCUMENT>\n", "a.htm")[0]
    ok, note = secondary.check_complete(b"<p>x</p><body>\n</TEXT>\n</DOCUMENT>\n", "a.htm")
    assert ok and "accepted" in note
    ok, note = secondary.check_complete(b'<html><body><ix:context id="c', "a.htm")
    assert not ok and "truncated" in note
    assert secondary.check_complete(b"<DOCUMENT>x</DOCUMENT>\n", "a.txt") == (True, "")
    ok, note = secondary.check_complete(b"plain text with no marker", "a.txt")
    assert ok and "accepted" in note


def test_truncated_bodies_are_retried_then_sent_to_errors(world, monkeypatch):
    raw, zp, calls = world
    cut = {"a.htm": BODIES["a.htm"][:500]}

    def download(src, path):
        calls.append(src.url)
        name = src.url.rsplit("/", 1)[-1]
        Path(path).write_bytes(cut.get(name, BODIES[name]))

    monkeypatch.setattr(fetch, "download", download)
    out = secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    st = dict(zip(out["adsh"], out["status"], strict=True))
    assert st[A1] == "error"
    assert sum(u.endswith("/a.htm") for u in calls) == secondary.COMPLETE_ATTEMPTS
    assert A1 not in secondary.read_index(raw / "sec/docs/INDEX.jsonl")
    errs = (raw / "sec/docs/ERRORS.jsonl").read_text()
    assert A1 in errs and "truncated" in errs
    # a later run retries it and, once whole, indexes it
    cut.clear()
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    assert A1 in secondary.read_index(raw / "sec/docs/INDEX.jsonl")


def test_refetch_replaces_index_lines_in_place(world, monkeypatch):
    raw, zp, calls = world
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, log=lambda s: None)
    index = raw / "sec/docs/INDEX.jsonl"
    before = [json.loads(x)["key"] for x in index.read_text().splitlines()]
    # simulate a truncated saved body, then find it offline and fetch it again
    rec = secondary.read_index(index)[A2]
    secondary.save_gzip(BODIES["b.htm"][:300], raw / rec["dest"])
    flagged = secondary.scan_incomplete(raw, workers=1)
    assert [f["key"] for f in flagged if not f["ok"]] == [A2]
    assert [f["key"] for f in flagged if f["ok"]] == [A3]  # plain text, accepted and noted
    calls.clear()
    secondary.download_documents(_filers(), raw=raw, zip_path=zp, refetch={A2}, log=lambda s: None)
    assert len(calls) == 1 and calls[0].endswith("/b.htm")
    after = [json.loads(x)["key"] for x in index.read_text().splitlines()]
    assert after == before
    assert secondary.scan_incomplete(raw, workers=1) == [f for f in flagged if f["ok"]]
    man = fetch.load_manifest(raw)
    assert man["sec_docs_index"].sha256 == hashlib.sha256(index.read_bytes()).hexdigest()
