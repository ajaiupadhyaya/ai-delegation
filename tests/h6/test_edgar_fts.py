"""H6 numerator (PAP §6, D18): EDGAR full-text search with exact-total bisection; distinct
CIKs per (year, FF49) among that year's full-index filers (C-39, C-49 (3))."""

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest

from aideleg.acquire import fetch
from aideleg.h6 import edgar

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures/sec"
FTS_SAMPLE = FIXTURES / "fts_sample.json"

Y0, Y1 = date(2024, 1, 1), date(2024, 12, 31)


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch):
    monkeypatch.setattr(edgar, "FTS_PAUSE", 0.0)


def _params(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


def _hit(hid: str, ciks, *, form="10-K", file_type="10-K", file_date="2024-03-01") -> dict:
    adsh = hid.split(":", 1)[0]
    return {
        "_id": hid,
        "_source": {
            "ciks": [f"{c:010d}" for c in ciks],
            "adsh": adsh,
            "form": form,
            "file_type": file_type,
            "file_date": file_date,
            "root_forms": ["10-K"],
        },
    }


def _resp(value: int, relation: str, hits: list[dict]) -> dict:
    return {"hits": {"total": {"value": value, "relation": relation}, "hits": hits}}


class FakeFts:
    """Responses keyed by (startdt, enddt, from): `ranges` maps (startdt, enddt) to
    (value, relation); a range listed as exact serves `value` synthetic hits, 100 per page."""

    def __init__(self, ranges: dict[tuple[str, str], tuple[int, str]]):
        self.ranges = ranges
        self.calls: list[tuple[str, str, int]] = []

    def body(self, url: str) -> dict:
        p = _params(url)
        s, e, off = p["startdt"], p["enddt"], int(p["from"])
        self.calls.append((s, e, off))
        value, relation = self.ranges[(s, e)]
        n = max(0, min(edgar.FTS_PAGE, value - off))
        tag = s if relation == "eq" else f"capped{s}"  # a capped page's hits are its own
        hits = [
            _hit(f"{tag}-{off + i:05d}:d.htm", [100000 + off + i], file_date=s) for i in range(n)
        ]
        return _resp(value, relation, hits)

    def get_json(self, src: fetch.Source) -> dict:
        return self.body(src.url)


def test_fixture_has_the_live_field_names():
    js = json.loads(FTS_SAMPLE.read_text())
    assert js["hits"]["total"]["relation"] == "eq"
    for h in js["hits"]["hits"]:
        assert {"ciks", "adsh", "form", "file_date", "file_type"} <= set(h["_source"])
        assert h["_id"].split(":", 1)[0] == h["_source"]["adsh"]
    rows = edgar.parse_fts(js, "computer vision")
    assert rows.columns == ["phrase", "cik", "adsh", "form", "file_date", "file_type", "_id"]
    assert rows["cik"].dtype == pl.Int64 and rows["file_date"].dtype == pl.Date
    assert rows.height == len(js["hits"]["hits"])


def test_fts_url_quotes_phrase_and_forms():
    url = edgar.fts_url("neural networks", Y0, Y1, 200)
    assert url.startswith(edgar.FTS_URL + "?")
    for part in (
        "q=%22neural%20networks%22",
        "dateRange=custom",
        "forms=10-K%2C10-K405%2C10-KT",
        "startdt=2024-01-01",
        "enddt=2024-12-31",
        "from=200",
    ):
        assert part in url


def test_fts_source_key_and_dest():
    src = edgar.fts_source("Neural networks", Y0, Y1, 200)
    assert src.key == "sec_fts/2024-01-01_2024-12-31/neural_networks/00200"
    assert src.dest == "sec/fts/2024/neural_networks/2024-01-01_2024-12-31_00200.json"
    assert src.url == edgar.fts_url("Neural networks", Y0, Y1, 200)


def test_fts_paginates_until_total(monkeypatch):
    fake = FakeFts({("2024-01-01", "2024-12-31"): (250, "eq")})
    monkeypatch.setattr(edgar, "_get_json", fake.get_json)
    df = edgar.fts_hits("machine learning", Y0, Y1)
    assert [c[2] for c in fake.calls] == [0, 100, 200]
    assert df.height == 250
    assert df.columns == ["phrase", "cik", "adsh", "form", "file_date", "file_type"]
    assert set(df["phrase"]) == {"machine learning"}


SPLIT = {
    ("2024-01-01", "2024-12-31"): (10_000, "gte"),
    ("2024-01-01", "2024-07-01"): (6000, "eq"),
    ("2024-07-02", "2024-12-31"): (3000, "eq"),
}


def test_fts_splits_range_when_total_hits_cap(monkeypatch):
    fake = FakeFts(SPLIT)
    monkeypatch.setattr(edgar, "_get_json", fake.get_json)
    df = edgar.fts_hits("artificial intelligence", Y0, Y1)
    ranges = {(s, e) for s, e, _ in fake.calls}
    assert ("2024-01-01", "2024-07-01") in ranges and ("2024-07-02", "2024-12-31") in ranges
    assert max(off for _, _, off in fake.calls) < edgar.FTS_CAP
    assert [c for c in fake.calls if c[:2] == ("2024-01-01", "2024-12-31")] == [
        ("2024-01-01", "2024-12-31", 0)
    ]
    want = {f"2024-01-01-{i:05d}" for i in range(6000)} | {
        f"2024-07-02-{i:05d}" for i in range(3000)
    }
    assert df.height == 9000 and set(df["adsh"]) == want


def test_fts_single_day_over_cap_raises(monkeypatch):
    day = date(2024, 3, 1)
    fake = FakeFts({("2024-03-01", "2024-03-01"): (10_000, "gte")})
    monkeypatch.setattr(edgar, "_get_json", fake.get_json)
    with pytest.raises(edgar.FtsCapError, match="2024-03-01"):
        edgar.fts_hits("artificial intelligence", day, day)


def test_fts_keeps_forms_and_one_row_per_cik(monkeypatch, capsys):
    hits = [
        _hit("0000000001-24-000001:a.htm", [1, 2]),  # co-registrants: one row each
        _hit("0000000003-24-000001:b.htm", [3], form="10-K/A", file_type="10-K/A"),
        _hit("0000000004-24-000001:c.htm", [], file_type="EX-99.1"),  # no CIK: no row
    ]
    monkeypatch.setattr(edgar, "_get_json", lambda src: _resp(3, "eq", hits))
    df = edgar.fts_hits("ChatGPT", Y0, Y1)
    assert sorted(df["cik"].to_list()) == [1, 2]
    assert set(df["form"]) == {"10-K"}
    out = capsys.readouterr().out
    assert "10-K/A" in out and "no CIK" in out


def test_fts_pages_short_of_the_total_raise(monkeypatch):
    """A document served twice (pagination shifted) means another was never served."""
    hits = [_hit("0000000001-24-000001:a.htm", [1]), _hit("0000000001-24-000001:a.htm", [1])]
    monkeypatch.setattr(edgar, "_get_json", lambda src: _resp(2, "eq", hits))
    with pytest.raises(edgar.FtsPageError, match="1 distinct documents"):
        edgar.fts_hits("ChatGPT", Y0, Y1)


FILERS = pl.DataFrame(
    {
        "year": [2024] * 5,
        "cik": [1, 2, 3, 4, 5],
        "adsh": ["a1", "a2", "a3", "a3", "a5"],
        "form": ["10-K"] * 5,
        "date_filed": [date(2024, 3, 1)] * 5,
        "sic": [7372, 7372, 6770, 6770, None],
        "ff49": [36, 36, 48, 48, None],
    },
    schema={
        "year": pl.Int64,
        "cik": pl.Int64,
        "adsh": pl.String,
        "form": pl.String,
        "date_filed": pl.Date,
        "sic": pl.Int64,
        "ff49": pl.Int64,
    },
)


def _hits(rows: list[tuple]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "phrase": pl.String,
            "cik": pl.Int64,
            "adsh": pl.String,
            "form": pl.String,
            "file_date": pl.Date,
            "file_type": pl.String,
        },
        orient="row",
    )


def test_numerator_counts_distinct_ciks_excluding_amendments():
    d = date(2024, 3, 1)
    hits = _hits(
        [
            ("artificial intelligence", 1, "a1", "10-K", d, "10-K"),
            ("machine learning", 1, "a1", "10-K", d, "10-K"),
            ("machine learning", 1, "a1", "10-K", d, "EX-99.1"),
            ("ChatGPT", 2, "a2x", "10-K/A", d, "10-K/A"),
            ("computer vision", 3, "a3", "10-K", d, "10-K"),
            ("computer vision", 4, "a3", "10-K", d, "10-K"),
            ("deep learning", 5, "a5", "10-K", d, "EX-99.1"),
            ("deep learning", 9, "a9", "10-K", d, "10-K"),
        ]
    )
    num = edgar.numerator(hits, FILERS)
    assert num.columns == ["year", "ff49", "n_talk", "n_exhibit_only"]
    assert num.height == 50  # FF49 1..49 and the null row, as in the denominator
    assert num.select("year", "ff49").equals(edgar.denominator(FILERS).select("year", "ff49"))
    assert num["n_talk"].sum() == 4  # {1, 3, 4, 5}
    assert num["n_exhibit_only"].sum() == 1  # CIK 5
    cell = {r["ff49"]: (r["n_talk"], r["n_exhibit_only"]) for r in num.iter_rows(named=True)}
    assert cell[36] == (1, 0) and cell[48] == (2, 0) and cell[None] == (1, 1)
    assert cell[1] == (0, 0)
    ood = edgar.out_of_denominator(hits, FILERS)
    assert ood.columns == ["year", "cik"] and ood.rows() == [(2024, 9)]


def test_numerator_assigns_hits_to_the_year_of_file_date():
    filers = FILERS.with_columns(pl.lit(2023, pl.Int64).alias("year"))
    hits = _hits([("deep learning", 1, "a1", "10-K", date(2024, 1, 5), "10-K")])
    assert edgar.numerator(hits, filers)["n_talk"].sum() == 0
    assert edgar.out_of_denominator(hits, filers).rows() == [(2024, 1)]


def _saving_download(fake: FakeFts):
    def download(src: fetch.Source, part: Path) -> None:
        Path(part).write_text(json.dumps(fake.body(src.url)))

    return download


def test_raw_response_recorded(monkeypatch, tmp_path: Path):
    fake = FakeFts({("2024-01-01", "2024-12-31"): (250, "eq")})
    monkeypatch.setattr(edgar, "RAW", tmp_path)
    monkeypatch.setattr(fetch, "_download", _saving_download(fake))
    edgar.fts_hits("machine learning", Y0, Y1)
    man = fetch.load_manifest(tmp_path)
    keys = sorted(man)
    assert keys == [
        f"sec_fts/2024-01-01_2024-12-31/machine_learning/{o:05d}" for o in (0, 100, 200)
    ]
    for k in keys:
        assert (tmp_path / man[k].dest).exists() and man[k].sha256


def test_hits_from_saved_equals_acquired(monkeypatch, tmp_path: Path):
    fake = FakeFts(SPLIT)
    monkeypatch.setattr(edgar, "RAW", tmp_path)
    monkeypatch.setattr(fetch, "_download", _saving_download(fake))
    got = edgar.fts_hits("artificial intelligence", Y0, Y1)

    def no_network(*a, **k):
        pytest.fail("network used")

    monkeypatch.setattr(fetch, "_download", no_network)
    monkeypatch.setattr(edgar, "_get_json", no_network)
    saved = edgar.hits_from_saved()
    order = ["phrase", "file_date", "adsh", "file_type", "cik"]
    assert saved.sort(order).equals(got.sort(order))
    assert saved.height == 9000
    assert not saved["adsh"].str.starts_with("capped").any()  # the split page 0 adds no row
    sub = edgar.hits_from_saved(["artificial intelligence"], date(2024, 7, 2), Y1)
    assert sub.height == 3000
    assert edgar.hits_from_saved(["machine learning"]).height == 0


def test_hits_from_saved_names_the_missing_page(monkeypatch, tmp_path: Path):
    fake = FakeFts({("2024-01-01", "2024-12-31"): (250, "eq")})
    monkeypatch.setattr(edgar, "RAW", tmp_path)
    monkeypatch.setattr(fetch, "_download", _saving_download(fake))
    edgar.fts_hits("machine learning", Y0, Y1)
    man = fetch.load_manifest(tmp_path)
    del man["sec_fts/2024-01-01_2024-12-31/machine_learning/00100"]
    fetch.write_manifest(tmp_path, man)
    with pytest.raises(FileNotFoundError, match="machine_learning/00100"):
        edgar.hits_from_saved()


ERROR_BODY = {"errorType": "ConnectionError", "errorMessage": "getaddrinfo EBUSY"}


def test_error_body_is_refetched_not_kept(monkeypatch, tmp_path: Path):
    """The server can answer HTTP 200 with an error JSON: it is never used or kept."""
    fake = FakeFts({("2024-01-01", "2024-12-31"): (50, "eq")})
    bodies = [ERROR_BODY]
    monkeypatch.setattr(edgar, "RAW", tmp_path)
    monkeypatch.setattr(edgar, "FTS_RETRY_SECONDS", 0.0)

    def download(src, part):
        body = bodies.pop(0) if bodies else fake.body(src.url)
        Path(part).write_text(json.dumps(body))

    monkeypatch.setattr(fetch, "_download", download)
    df = edgar.fts_hits("machine learning", Y0, Y1)
    assert df.height == 50
    rec = fetch.load_manifest(tmp_path)["sec_fts/2024-01-01_2024-12-31/machine_learning/00000"]
    assert "hits" in json.loads((tmp_path / rec.dest).read_text())


def test_persistent_error_body_raises_and_drops_the_record(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(edgar, "RAW", tmp_path)
    monkeypatch.setattr(edgar, "FTS_RETRY_SECONDS", 0.0)
    monkeypatch.setattr(
        fetch, "_download", lambda src, part: Path(part).write_text(json.dumps(ERROR_BODY))
    )
    with pytest.raises(edgar.FtsServerError, match="ConnectionError"):
        edgar.fts_hits("machine learning", Y0, Y1)
    assert fetch.load_manifest(tmp_path) == {}
    assert not list((tmp_path / "sec").rglob("*.json"))
