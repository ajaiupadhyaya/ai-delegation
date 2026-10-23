"""Protocol guards (PAP §0.5): tmp git repos for the refusals, this repo for the invariants."""

import importlib
import json
import subprocess
from pathlib import Path

import pytest

from aideleg.config import ROOT
from aideleg.robustness import guards, upstream

MD, ATTEMPT = guards.H5_FILES
RQ1_JSON, RQ1_MD, RQ1_LOG, RQ1_ATTEMPT = guards.RQ1_FILES
# Plan 3's guard module, reached through the adapter's re-export, for its PINNED blob IDs.
_rq3_guard = importlib.import_module(upstream.assert_confirmatory_recorded.__module__)


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.org")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "unrelated.txt").write_text("x\n")
    _git(tmp_path, "add", "unrelated.txt")
    _git(tmp_path, "commit", "-q", "-m", "unrelated")
    return tmp_path


def _copy_h5(repo: Path) -> None:
    """The exact committed bytes of the confirmatory record (blob-pinned in Plan 3's guard)."""
    for rel in guards.H5_FILES:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((ROOT / rel).read_bytes())


def _commit(repo: Path, *paths: str, msg: str = "record") -> None:
    _git(repo, "add", *paths)
    _git(repo, "commit", "-q", "-m", msg)


# --- H5: require_confirmatory_committed


def test_guard_refuses_untracked_confirmatory(repo):
    _copy_h5(repo)
    with pytest.raises(guards.ProtocolError) as exc:
        guards.require_confirmatory_committed(repo)
    assert isinstance(exc.value.__cause__, upstream.ConfirmatoryNotRecorded)
    _commit(repo, *guards.H5_FILES)
    guards.require_confirmatory_committed(repo)


def test_guard_refuses_modified_confirmatory(repo):
    _copy_h5(repo)
    _commit(repo, *guards.H5_FILES)
    with (repo / MD).open("ab") as fh:
        fh.write(b"\nappended\n")
    with pytest.raises(guards.ProtocolError, match="modified"):
        guards.require_confirmatory_committed(repo)


def test_guard_refuses_attempt_only_record(repo, monkeypatch):
    _copy_h5(repo)
    lines = (repo / MD).read_bytes().split(b"\n")
    lines[0] = b"# Confirmatory test of H5 and H5b: attempt failed"
    (repo / MD).write_bytes(b"\n".join(lines))
    _commit(repo, *guards.H5_FILES)
    # pin the edited record's own blobs, so the refusal is the heading's, not the pin's
    pinned = {rel: _git(repo, "hash-object", rel) for rel in guards.H5_FILES}
    monkeypatch.setattr(_rq3_guard, "PINNED", pinned)
    with pytest.raises(guards.ProtocolError, match="attempt"):
        guards.require_confirmatory_committed(repo)


# --- RQ1: require_rq1_run_committed


def _write_rq1(repo: Path, *, scrambled: bool = False) -> None:
    (repo / RQ1_JSON).parent.mkdir(parents=True, exist_ok=True)
    meta = {"scrambled": scrambled, "blobs": {"src/a.py": "x"}}
    (repo / RQ1_JSON).write_text(json.dumps({"meta": meta, "results": {}}) + "\n")
    for rel in (RQ1_MD, RQ1_LOG, RQ1_ATTEMPT):
        (repo / rel).write_text(f"{rel}\n")


def test_rq1_guard_needs_four_unscrambled_files(repo):
    _write_rq1(repo)
    _commit(repo, *guards.RQ1_FILES)
    head = _git(repo, "rev-parse", "HEAD")
    (repo / "later.txt").write_text("y\n")
    _commit(repo, "later.txt", msg="later")
    assert guards.require_rq1_run_committed(repo) == head


def test_rq1_guard_refuses_untracked_log(repo):
    _write_rq1(repo)
    _commit(repo, RQ1_JSON, RQ1_MD, RQ1_ATTEMPT)
    with pytest.raises(guards.ProtocolError, match="log"):
        guards.require_rq1_run_committed(repo)


def test_rq1_guard_refuses_staged_only_file(repo):
    _write_rq1(repo)
    _commit(repo, RQ1_JSON, RQ1_MD, RQ1_ATTEMPT)
    _git(repo, "add", RQ1_LOG)
    with pytest.raises(guards.ProtocolError, match="log"):
        guards.require_rq1_run_committed(repo)


def test_rq1_guard_refuses_modified_md(repo):
    _write_rq1(repo)
    _commit(repo, *guards.RQ1_FILES)
    (repo / RQ1_MD).write_text("edited\n")
    with pytest.raises(guards.ProtocolError, match="modified"):
        guards.require_rq1_run_committed(repo)


def test_rq1_guard_refuses_scrambled_run(repo):
    _write_rq1(repo, scrambled=True)
    _commit(repo, *guards.RQ1_FILES)
    with pytest.raises(guards.ProtocolError, match="scrambled"):
        guards.require_rq1_run_committed(repo)


def test_rq1_guard_refuses_missing_scrambled_flag(repo):
    _write_rq1(repo)
    (repo / RQ1_JSON).write_text(json.dumps({"meta": {}}) + "\n")
    _commit(repo, *guards.RQ1_FILES)
    with pytest.raises(guards.ProtocolError, match="scrambled"):
        guards.require_rq1_run_committed(repo)


def test_protected_files_are_meta_blobs(tmp_path):
    (tmp_path / RQ1_JSON).parent.mkdir(parents=True)
    meta = {"blobs": {"src/b.py": "y", "src/a.py": "x"}}
    (tmp_path / RQ1_JSON).write_text(json.dumps({"meta": meta}))
    assert guards.protected_files(tmp_path) == ["src/a.py", "src/b.py"]


# --- this repo


def test_guards_pass_on_this_repo():
    guards.require_confirmatory_committed()
    assert guards.require_rq1_run_committed() == _git(
        ROOT, "log", "-1", "--format=%H", "--", RQ1_JSON
    )


def test_confirmatory_files_untouched():
    blobs = json.loads((ROOT / RQ1_JSON).read_text(encoding="utf-8"))["meta"]["blobs"]
    protected = guards.protected_files()
    assert protected
    for rel in protected:
        assert _git(ROOT, "hash-object", rel) == blobs[rel], rel
    rq1_commit = guards.require_rq1_run_committed()
    for rel in guards.RQ1_FILES:
        assert (
            subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--quiet", rq1_commit, "HEAD", "--", rel]
            ).returncode
            == 0
        ), rel
    h5_commit = _git(ROOT, "log", "-1", "--format=%H", "--", MD)
    assert h5_commit
    for rel in guards.H5_FILES:
        assert (
            subprocess.run(
                ["git", "-C", str(ROOT), "diff", "--quiet", h5_commit, "HEAD", "--", rel]
            ).returncode
            == 0
        ), rel
    assert (
        subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "diff",
                "--quiet",
                "pap-v1",
                "HEAD",
                "--",
                "src/aideleg/confirm_h5.py",
                "src/aideleg/power.py",
                "src/aideleg/market",
            ]
        ).returncode
        == 0
    )
