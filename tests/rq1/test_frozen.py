"""The frozen-code guard of P-RQ1 (PAP §0.5): after the first real run, the bound RQ1 code and
the numerical library versions must stay as that run recorded them.

- With the result JSON (not scrambled): every blob in `meta.blobs` and every version in
  `meta.versions` (numpy, scipy, polars, statsmodels) must still hold.
- With the attempt marker but no JSON (a failed attempt): every `BOUND_FILES` blob must equal
  its blob at the HEAD recorded in the marker.
- Otherwise there is nothing to bind yet, and the test skips.
"""

import importlib.metadata
import json
import subprocess
from pathlib import Path

import pytest

from aideleg.config import ROOT
from aideleg.rq1.confirm import BOUND_FILES, JSON_NAME, MARKER_NAME, OUT_DIR

PACKAGES = ("numpy", "scipy", "polars", "statsmodels")
MESSAGE = "bound RQ1 code changed after the P-RQ1 first run: record a §11 deviation (PAP §0.5)"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True).stdout.strip()


def _blob_changes(repo: Path, recorded: dict[str, str | None]) -> list[str]:
    out = []
    for path, blob in recorded.items():
        now = _git(repo, "hash-object", path) if (repo / path).is_file() else ""
        if not blob or now != blob:
            out.append(f"{path}: {blob or 'unrecorded'} -> {now or 'missing'}")
    return out


def bound_changes(out_dir: Path = OUT_DIR, repo: Path = ROOT,
                  paths: tuple[str, ...] = BOUND_FILES) -> list[str] | None:
    """The changes since the first run, or None when there is nothing to bind yet."""
    result, marker = out_dir / JSON_NAME, out_dir / MARKER_NAME
    if result.exists():
        meta = json.loads(result.read_text(encoding="utf-8"))["meta"]
        if meta.get("scrambled", True):
            return None
        changed = _blob_changes(repo, meta["blobs"])
        for pkg in PACKAGES:
            now = importlib.metadata.version(pkg)
            if now != meta["versions"][pkg]:
                changed.append(f"{pkg}: {meta['versions'][pkg]} -> {now}")
        return changed
    if marker.exists():
        head = marker.read_text(encoding="utf-8").split()[-1]
        return _blob_changes(repo, {p: _git(repo, "rev-parse", f"{head}:{p}") for p in paths})
    return None


def test_bound_code_unchanged_since_first_run():
    changed = bound_changes()
    if changed is None:
        pytest.skip("no P-RQ1 first run or attempt yet")
    assert not changed, f"{MESSAGE}: {'; '.join(changed)}"


def _commit(repo: Path, msg: str) -> str:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", "commit", "-q", "-am", msg], check=True)
    return _git(repo, "rev-parse", "HEAD")


def test_attempt_marker_binds_to_its_head(tmp_path):
    repo, out = tmp_path / "repo", tmp_path / "out"
    (repo / "src").mkdir(parents=True)
    out.mkdir()
    (repo / "src/a.py").write_text("a = 1\n")
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
    head = _commit(repo, "bound")
    assert bound_changes(out, repo, ("src/a.py",)) is None  # nothing to bind yet
    (out / MARKER_NAME).write_text(f"2026-10-22T00:00:00Z\n{head}\n")
    assert bound_changes(out, repo, ("src/a.py",)) == []
    (repo / "src/a.py").write_text("a = 2\n")
    changed = bound_changes(out, repo, ("src/a.py",))
    assert len(changed) == 1 and changed[0].startswith("src/a.py:")
    _commit(repo, "edit after the attempt")  # committing the edit does not move the binding
    assert len(bound_changes(out, repo, ("src/a.py",))) == 1


def test_scrambled_result_is_not_bound(tmp_path):
    (tmp_path / JSON_NAME).write_text(json.dumps({"meta": {"scrambled": True}}))
    (tmp_path / MARKER_NAME).write_text("t\nabc\n")
    assert bound_changes(tmp_path) is None
