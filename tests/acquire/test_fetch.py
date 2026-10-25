import hashlib
import io
import zipfile

import pytest
import requests

from aideleg.acquire import fetch, http

UA = "Test Person research test@example.org"


@pytest.fixture(autouse=True)
def _contact(monkeypatch):
    monkeypatch.setenv(http.CONTACT_ENV, UA)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200, headers=None, fail_after=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {}
        self.fail_after = fail_after

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size=1 << 16):
        if self.fail_after is not None:
            yield self.body[: self.fail_after]
            raise requests.exceptions.ChunkedEncodingError("connection broken")
        for i in range(0, len(self.body), chunk_size):
            yield self.body[i : i + chunk_size]

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


@pytest.fixture
def patch_session(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda s: None)

    def install(*responses):
        session = FakeSession(responses)
        monkeypatch.setattr(http, "session_for", lambda url: session)
        return session

    return install


def test_fetch_writes_file_and_sha256(tmp_path, patch_session):
    patch_session(FakeResponse(b"abc"))
    rec = fetch.fetch(fetch.Source("k", "https://x.test/a.bin", "sub/a.bin"), raw_dir=tmp_path)
    assert (tmp_path / "sub/a.bin").read_bytes() == b"abc"
    assert rec.sha256 == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert rec.bytes == 3
    assert not list(tmp_path.rglob("*.part"))
    assert fetch.load_manifest(tmp_path)["k"] == rec


def test_fetch_skips_when_present_and_hash_matches(tmp_path, patch_session):
    session = patch_session(FakeResponse(b"abc"))
    src = fetch.Source("k", "https://x.test/a.bin", "a.bin")
    first = fetch.fetch(src, raw_dir=tmp_path)
    second = fetch.fetch(src, raw_dir=tmp_path)
    assert session.calls == 1
    assert second == first


def test_fetch_refetches_when_file_changed_or_forced(tmp_path, patch_session):
    session = patch_session(FakeResponse(b"abc"), FakeResponse(b"abc"), FakeResponse(b"abc"))
    src = fetch.Source("k", "https://x.test/a.bin", "a.bin")
    fetch.fetch(src, raw_dir=tmp_path)
    (tmp_path / "a.bin").write_bytes(b"tampered")
    fetch.fetch(src, raw_dir=tmp_path)
    assert session.calls == 2
    fetch.fetch(src, raw_dir=tmp_path, force=True)
    assert session.calls == 3


def test_fetch_rejects_html_error_page(tmp_path, patch_session):
    patch_session(FakeResponse(b"<!DOCTYPE HTML PUBLIC><html>Access Denied</html>"))
    with pytest.raises(fetch.FetchError):
        fetch.fetch(fetch.Source("k", "https://www.bls.gov/a.xlsx", "a.xlsx"), raw_dir=tmp_path)
    assert not (tmp_path / "a.xlsx").exists()
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_allows_html_when_dest_is_html(tmp_path, patch_session):
    patch_session(FakeResponse(b"<!DOCTYPE HTML><html></html>"))
    rec = fetch.fetch(fetch.Source("k", "https://x.test/p", "p.html"), raw_dir=tmp_path)
    assert rec.bytes > 0


def test_fetch_retries_5xx_then_succeeds(tmp_path, patch_session):
    session = patch_session(FakeResponse(b"", 503), FakeResponse(b"", 429), FakeResponse(b"abc"))
    rec = fetch.fetch(fetch.Source("k", "https://x.test/a", "a.bin"), raw_dir=tmp_path)
    assert session.calls == 3
    assert rec.bytes == 3


def test_fetch_gives_up_after_three_attempts(tmp_path, patch_session):
    session = patch_session(*[FakeResponse(b"", 500) for _ in range(5)])
    with pytest.raises(fetch.FetchError):
        fetch.fetch(fetch.Source("k", "https://x.test/a", "a.bin"), raw_dir=tmp_path)
    assert session.calls == 3


def test_bls_and_sec_get_contact_user_agent():
    assert http.session_for("https://www.bls.gov/x").headers["User-Agent"] == UA
    assert http.session_for("https://data.sec.gov/x").headers["User-Agent"] == UA
    assert http.session_for("https://example.org/x").headers["User-Agent"] != UA


def test_contact_user_agent_required(monkeypatch):
    monkeypatch.delenv(http.CONTACT_ENV)
    with pytest.raises(RuntimeError, match=http.CONTACT_ENV):
        http.session_for("https://www.sec.gov/x")
    assert "User-Agent" in http.session_for("https://example.org/x").headers


def test_sec_session_throttles_to_ten_per_second(monkeypatch):
    monkeypatch.setattr(http, "_last_request", None)
    clock = {"t": 100.0}
    slept = []
    monkeypatch.setattr(http.time, "monotonic", lambda: clock["t"])

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    monkeypatch.setattr(http.time, "sleep", fake_sleep)
    session = http.session_for("https://data.sec.gov/x")
    monkeypatch.setattr(http.requests.Session, "request", lambda self, *a, **k: "ok")
    for _ in range(3):
        session.get("https://data.sec.gov/x")
    assert len(slept) == 2
    assert all(s >= 0.1 - 1e-9 for s in slept)


def test_unzip_extracts_next_to_archive(tmp_path, patch_session):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.csv", "x,y\n1,2\n")
    patch_session(FakeResponse(buf.getvalue()))
    rec = fetch.fetch(
        fetch.Source("k", "https://x.test/d.zip", "ff/d.zip", unzip=True), raw_dir=tmp_path
    )
    assert (tmp_path / "ff/d/a.csv").read_text() == "x,y\n1,2\n"
    assert rec.sha256 == hashlib.sha256(buf.getvalue()).hexdigest()


def test_manifest_roundtrip(tmp_path):
    rec = fetch.FetchRecord("k", "u", "d", "2026-10-21T00:00:00Z", 3, "ab")
    fetch.write_manifest(tmp_path, {"k": rec})
    assert fetch.load_manifest(tmp_path) == {"k": rec}
    assert fetch.load_manifest(tmp_path / "missing") == {}


def test_sec_throttle_is_shared_across_sessions(monkeypatch):
    monkeypatch.setattr(http, "_last_request", None)
    clock = {"t": 100.0}
    slept = []

    def fake_sleep(s):
        slept.append(s)
        clock["t"] += s

    monkeypatch.setattr(http.time, "monotonic", lambda: clock["t"])
    monkeypatch.setattr(http.time, "sleep", fake_sleep)
    monkeypatch.setattr(http.requests.Session, "request", lambda self, *a, **k: "ok")
    http.session_for("https://data.sec.gov/a").get("https://data.sec.gov/a")
    http.session_for("https://data.sec.gov/b").get("https://data.sec.gov/b")
    assert len(slept) == 1
    assert slept[0] >= 0.1 - 1e-9


def test_fetch_retries_midstream_failure_then_succeeds(tmp_path, patch_session):
    session = patch_session(FakeResponse(b"abcdef", fail_after=3), FakeResponse(b"abcdef"))
    rec = fetch.fetch(fetch.Source("k", "https://x.test/a", "a.bin"), raw_dir=tmp_path)
    assert session.calls == 2
    assert (tmp_path / "a.bin").read_bytes() == b"abcdef"
    assert rec.bytes == 6


def test_fetch_midstream_failure_every_time_raises_fetch_error(tmp_path, patch_session):
    patch_session(*[FakeResponse(b"abcdef", fail_after=3) for _ in range(3)])
    with pytest.raises(fetch.FetchError):
        fetch.fetch(fetch.Source("k", "https://x.test/a", "a.bin"), raw_dir=tmp_path)
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_truncated_body_raises_fetch_error(tmp_path, patch_session):
    hdr = {"Content-Length": "10"}
    session = patch_session(*[FakeResponse(b"abc", headers=hdr) for _ in range(3)])
    with pytest.raises(fetch.FetchError, match="truncated"):
        fetch.fetch(fetch.Source("k", "https://x.test/a", "a.bin"), raw_dir=tmp_path)
    assert session.calls == 3
    assert not (tmp_path / "a.bin").exists()


def test_refetch_clears_the_extracted_directory(tmp_path, patch_session):
    # K2: a stale member from an earlier archive must not survive a refetch
    def _zip(**members):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for name, text in members.items():
                z.writestr(name, text)
        return buf.getvalue()

    patch_session(FakeResponse(_zip(**{"old.csv": "1\n"})),
                  FakeResponse(_zip(**{"new.csv": "2\n"})))
    src = fetch.Source("k", "https://x.test/d.zip", "ff/d.zip", unzip=True)
    fetch.fetch(src, raw_dir=tmp_path)
    assert (tmp_path / "ff/d/old.csv").exists()
    fetch.fetch(src, raw_dir=tmp_path, force=True)
    assert sorted(p.name for p in (tmp_path / "ff/d").iterdir()) == ["new.csv"]
