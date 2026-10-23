"""Download raw files once, verify them, and record them in a committed manifest."""

import hashlib
import json
import shutil
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from aideleg.acquire import http
from aideleg.config import RAW

MANIFEST_NAME = "MANIFEST.json"
ATTEMPTS = 3
BACKOFF_SECONDS = 2.0
TIMEOUT = 60


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    dest: str  # path relative to the raw directory
    unzip: bool = False


@dataclass
class FetchRecord:
    key: str
    url: str
    dest: str
    retrieved_utc: str
    bytes: int
    sha256: str


def load_manifest(raw_dir: Path) -> dict[str, FetchRecord]:
    path = Path(raw_dir) / MANIFEST_NAME
    if not path.exists():
        return {}
    return {k: FetchRecord(**v) for k, v in json.loads(path.read_text()).items()}


def write_manifest(raw_dir: Path, records: dict[str, FetchRecord]) -> None:
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    body = {k: asdict(records[k]) for k in sorted(records)}
    (raw_dir / MANIFEST_NAME).write_text(json.dumps(body, indent=2) + "\n")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _unzip_dir(target: Path) -> Path:
    return target.with_suffix("")


def _is_current(src: Source, target: Path, rec: FetchRecord | None) -> bool:
    if rec is None or rec.url != src.url or rec.dest != src.dest or not target.exists():
        return False
    if src.unzip and not _unzip_dir(target).is_dir():
        return False
    return _sha256(target) == rec.sha256


def _download(src: Source, part: Path) -> None:
    last = "no attempt made"
    for attempt in range(ATTEMPTS):
        if attempt:
            time.sleep(BACKOFF_SECONDS * 2 ** (attempt - 1))
        try:
            resp = http.session_for(src.url).get(src.url, stream=True, timeout=TIMEOUT)
            try:
                if resp.status_code >= 500 or resp.status_code == 429:
                    last = f"HTTP {resp.status_code}"
                    continue
                try:
                    resp.raise_for_status()
                except Exception as exc:
                    raise FetchError(f"{src.url}: {exc}") from exc
                written = 0
                with part.open("wb") as f:
                    for chunk in resp.iter_content(1 << 16):
                        f.write(chunk)
                        written += len(chunk)
                headers = getattr(resp, "headers", None) or {}
                expected = headers.get("Content-Length")
                # A compressed body is decoded on the fly, so its length cannot be compared.
                if expected is not None and not headers.get("Content-Encoding"):
                    if written != int(expected):
                        last = f"truncated body ({written} of {expected} bytes)"
                        continue
                return
            finally:
                resp.close()
        except OSError as exc:  # requests exceptions, including mid-stream ones, subclass OSError
            last = repr(exc)
    raise FetchError(f"{src.url}: gave up after {ATTEMPTS} attempts ({last})")


download = _download  # public: callers that stream to a path of their own (H6 sets)


def fetch(src: Source, raw_dir: Path = RAW, force: bool = False) -> FetchRecord:
    raw_dir = Path(raw_dir)
    target = raw_dir / src.dest
    manifest = load_manifest(raw_dir)
    existing = manifest.get(src.key)
    if not force and existing is not None and _is_current(src, target, existing):
        return existing

    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        _download(src, part)
        with part.open("rb") as f:
            head = f.read(64).lstrip().lower()
        if head.startswith((b"<!doctype html", b"<html")) and not src.dest.lower().endswith(
            (".html", ".htm")
        ):
            raise FetchError(f"{src.url}: got an HTML page, not {src.dest} (access denied?)")
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)

    if src.unzip:
        out_dir = _unzip_dir(target)
        if out_dir.exists():  # a refetch never leaves members of an earlier archive behind
            shutil.rmtree(out_dir)
        try:
            with zipfile.ZipFile(target) as z:
                z.extractall(out_dir)
        except zipfile.BadZipFile as exc:
            target.unlink()
            raise FetchError(f"{src.url}: not a valid zip archive") from exc

    record = FetchRecord(
        key=src.key,
        url=src.url,
        dest=src.dest,
        retrieved_utc=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        bytes=target.stat().st_size,
        sha256=_sha256(target),
    )
    manifest[src.key] = record
    write_manifest(raw_dir, manifest)
    return record
