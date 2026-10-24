"""Replication helpers (Task 33): seed `data/raw` from a frozen archive, and check the sources.

- `from_dir(DIR)` copies every MANIFEST file from `DIR/<dest>`, refusing (and naming the key)
  any file whose SHA-256 differs from the committed MANIFEST, re-extracts the zips the registry
  marks `unzip`, and restores the 10-K documents of `sec/docs/INDEX.jsonl`, refusing any whose
  uncompressed SHA-256 or byte count differs from its INDEX line, or that is missing. Nothing
  is written for a refused key.
- `check_download()` downloads every non-bulk MANIFEST file into a temporary directory and
  writes a table of key and match (yes/no) to `docs/replication/download_check.md`. It never
  touches `data/raw`. The bulk SEC sets (the full-text-search responses and the 10-K documents)
  are not re-downloaded; `from_dir` verifies them from the frozen archive.
"""

import gzip
import hashlib
import json
import shutil
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path

from aideleg.acquire import fetch, sources
from aideleg.config import RAW, ROOT

DOCS_INDEX_KEY = "sec_docs_index"
FTS_PREFIX = "sec_fts/"
BULK_NOTE = "not re-downloaded (bulk; verified from the frozen archive by --from-dir)"
DOWNLOAD_CHECK = ROOT / "docs/replication/download_check.md"


def _safe(base: Path, rel: str) -> Path:
    """`base/rel`, refusing a path that leaves `base`."""
    p = (base / rel).resolve()
    if base.resolve() not in p.parents:
        raise ValueError(f"{rel!r} leaves {base}")
    return p


def _copy_checked(src: Path, dst: Path, check: Callable[[bytes], str | None]) -> str | None:
    """Copy `src` to `dst` through a `.part` file when `check(body)` returns None; otherwise
    leave `dst` unwritten and return the reason."""
    if not src.is_file():
        return f"missing from the archive: {src}"
    body = src.read_bytes()
    reason = check(body)
    if reason is not None:
        return reason
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    try:
        part.write_bytes(body)
        part.replace(dst)
    finally:
        part.unlink(missing_ok=True)
    return None


def _copy_hashed(src: Path, dst: Path, sha256: str, nbytes: int) -> str | None:
    """Stream `src` to `dst` through a `.part` file, hashing as it goes; keep `dst` only when
    the SHA-256 and byte count match the MANIFEST, otherwise return the reason."""
    if not src.is_file():
        return f"missing from the archive: {src}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    part = dst.with_name(dst.name + ".part")
    h, n = hashlib.sha256(), 0
    try:
        with src.open("rb") as fi, part.open("wb") as fo:
            for chunk in iter(lambda: fi.read(1 << 20), b""):
                h.update(chunk)
                n += len(chunk)
                fo.write(chunk)
        got = h.hexdigest()
        if got != sha256 or n != nbytes:
            return (
                f"SHA-256 {got[:12]} ({n} bytes) differs from the MANIFEST's "
                f"{sha256[:12]} ({nbytes} bytes)"
            )
        part.replace(dst)
        return None
    finally:
        part.unlink(missing_ok=True)


def _doc_check(rec: dict) -> Callable[[bytes], str | None]:
    def check(body: bytes) -> str | None:
        try:
            data = gzip.decompress(body)
        except (OSError, EOFError) as exc:
            return f"not a readable gzip file ({exc})"
        got = hashlib.sha256(data).hexdigest()
        if got != rec["sha256"] or len(data) != rec["bytes"]:
            return (
                f"uncompressed SHA-256 {got[:12]} ({len(data)} bytes) differs from "
                f"INDEX.jsonl's {rec['sha256'][:12]} ({rec['bytes']} bytes)"
            )
        return None

    return check


def _unzip(target: Path) -> None:
    out_dir = target.with_suffix("")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    with zipfile.ZipFile(target) as z:
        z.extractall(out_dir)


def read_index(path: Path) -> dict[str, dict]:
    """key -> INDEX.jsonl record; a later line for the same key wins (as Plan 3 reads it)."""
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rec = json.loads(line)
            out[rec["key"]] = rec
    return out


def from_dir(
    src_dir: Path, raw_dir: Path = RAW, log: Callable[[str], None] = print
) -> list[tuple[str, str]]:
    """Seed `raw_dir` from the frozen archive `src_dir`; return the refused `(key, reason)`s."""
    src_dir, raw_dir = Path(src_dir), Path(raw_dir)
    if src_dir.resolve() == raw_dir.resolve():
        raise ValueError(f"--from-dir is the same directory as the raw directory ({raw_dir})")
    manifest = fetch.load_manifest(raw_dir)
    if not manifest:
        raise ValueError(f"no {fetch.MANIFEST_NAME} in {raw_dir}")
    refused: list[tuple[str, str]] = []
    for key in sorted(manifest):
        rec = manifest[key]
        target = _safe(raw_dir, rec.dest)
        reason = _copy_hashed(_safe(src_dir, rec.dest), target, rec.sha256, rec.bytes)
        if reason is None:
            src = sources._BY_KEY.get(key)
            if src is not None and src.unzip:
                try:
                    _unzip(target)
                except zipfile.BadZipFile as exc:
                    reason = f"not a valid zip archive ({exc})"
        if reason is not None:
            refused.append((key, reason))
    n_files = len(manifest) - len(refused)
    log(f"{n_files} of {len(manifest)} MANIFEST files copied and verified")

    if DOCS_INDEX_KEY in manifest:
        if any(k == DOCS_INDEX_KEY for k, _ in refused):
            refused.append(("sec/docs/**", "not restored: INDEX.jsonl was refused"))
        else:
            index = read_index(_safe(raw_dir, manifest[DOCS_INDEX_KEY].dest))
            n_bad = len(refused)
            for key, rec in index.items():
                if not rec["dest"].startswith("sec/docs/"):
                    refused.append((key, f"INDEX dest {rec['dest']!r} is not under sec/docs/"))
                    continue
                reason = _copy_checked(
                    _safe(src_dir, rec["dest"]), _safe(raw_dir, rec["dest"]), _doc_check(rec)
                )
                if reason is not None:
                    refused.append((key, reason))
            ok = len(index) - (len(refused) - n_bad)
            log(f"{ok} of {len(index)} 10-K documents copied and verified (INDEX.jsonl)")
    return refused


def _bulk(key: str) -> bool:
    return key.startswith(FTS_PREFIX) or key == DOCS_INDEX_KEY


def check_download(
    out: Path = DOWNLOAD_CHECK, raw_dir: Path = RAW, log: Callable[[str], None] = print
) -> list[dict]:
    """Download every non-bulk MANIFEST file into a temporary directory, compare its SHA-256
    with the MANIFEST and write the table to `out`. `raw_dir` is only read (its MANIFEST)."""
    manifest = fetch.load_manifest(Path(raw_dir))
    rows: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="aideleg-download-check-") as tmp:
        for key in sorted(k for k in manifest if not _bulk(k)):
            rec = manifest[key]
            path = Path(tmp) / f"{len(rows):04d}.download"
            try:
                fetch.download(fetch.Source(key, rec.url, rec.dest), path)
            except fetch.FetchError as exc:
                rows.append({"key": key, "match": "no", "note": f"download failed: {exc}"})
                log(f"{key}: download failed")
                continue
            sha = fetch._sha256(path)
            size = path.stat().st_size
            path.unlink()
            match = sha == rec.sha256
            note = (
                ""
                if match
                else (
                    f"now {sha[:12]} ({size} bytes); MANIFEST {rec.sha256[:12]} "
                    f"({rec.bytes} bytes, retrieved {rec.retrieved_utc})"
                )
            )
            rows.append({"key": key, "match": "yes" if match else "no", "note": note})
            log(f"{key}: {'match' if match else 'MISMATCH'}")
    n_fts = sum(k.startswith(FTS_PREFIX) for k in manifest)
    bulk = []
    if n_fts:
        bulk.append((f"{FTS_PREFIX}* ({n_fts} full-text-search responses)", BULK_NOTE))
    if DOCS_INDEX_KEY in manifest:
        bulk.append((f"{DOCS_INDEX_KEY} (INDEX.jsonl and the 10-K documents it lists)", BULK_NOTE))
    _write_table(Path(out), rows, bulk)
    return rows


def _write_table(out: Path, rows: list[dict], bulk: list[tuple[str, str]]) -> None:
    n_yes = sum(r["match"] == "yes" for r in rows)
    lines = [
        "# Download check",
        "",
        "Generated by `uv run python -m aideleg.acquire --check-download`. Every non-bulk file "
        "in `data/raw/MANIFEST.json` was downloaded again into a temporary directory (never "
        "`data/raw`) and its SHA-256 compared with the MANIFEST. A mismatch means the source "
        "now serves different bytes than the frozen archive the results were built from; the "
        "replication seeds `data/raw` from that archive (`--from-dir`), which refuses any file "
        "whose SHA-256 differs from the MANIFEST.",
        "",
        f"{n_yes} of {len(rows)} re-downloaded files match; {len(rows) - n_yes} do not.",
        "",
        "| key | match | note |",
        "|---|---|---|",
        *[f"| `{r['key']}` | {r['match']} | {r['note']} |" for r in rows],
        "",
        "## Bulk SEC sets",
        "",
        "| set | status |",
        "|---|---|",
        *[f"| `{name.split(' ', 1)[0]}` {name.split(' ', 1)[1]} | {note} |" for name, note in bulk],
        "",
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines))
