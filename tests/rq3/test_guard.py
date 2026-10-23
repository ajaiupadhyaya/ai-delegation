"""The post-seal guard, on tmp git repos only."""

import subprocess
from pathlib import Path

import pytest

from aideleg.rq3 import guard

MD, ATTEMPT = guard.CONFIRMATORY


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


@pytest.fixture
def repo(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(guard, "PINNED", dict(guard.PINNED))
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.org")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "unrelated.txt").write_text("x\n")
    _git(tmp_path, "add", "unrelated.txt")
    _git(tmp_path, "commit", "-q", "-m", "unrelated")
    return tmp_path


def _write(repo: Path, heading: str) -> None:
    (repo / MD).parent.mkdir(parents=True, exist_ok=True)
    (repo / MD).write_text(f"{heading}\n\nbody\n")
    (repo / ATTEMPT).write_text("started_utc: x\n")


def _blob(repo: Path, rel: str) -> str:
    return subprocess.run(["git", "-C", str(repo), "hash-object", rel], capture_output=True,
                          text=True, check=True).stdout.strip()


def _commit(repo: Path, pin: bool = True) -> None:
    _git(repo, "add", MD, ATTEMPT)
    _git(repo, "commit", "-q", "-m", "record")
    if pin:  # the tmp repo's own record stands in for ebe59be
        guard.PINNED.update({rel: _blob(repo, rel) for rel in guard.CONFIRMATORY})


def test_guard_refuses_without_record(repo):
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="not committed"):
        guard.assert_confirmatory_recorded(repo)


def test_guard_refuses_uncommitted_record(repo):
    _write(repo, guard.RESULT_HEADING)
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="not committed"):
        guard.assert_confirmatory_recorded(repo)


def test_guard_refuses_staged_but_uncommitted_record(repo):
    _write(repo, guard.RESULT_HEADING)
    _git(repo, "add", MD, ATTEMPT)
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="not committed"):
        guard.assert_confirmatory_recorded(repo)


def test_guard_refuses_edited_record(repo):
    _write(repo, guard.RESULT_HEADING)
    _commit(repo)
    (repo / MD).write_text(f"{guard.RESULT_HEADING}\n\nedited\n")
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="modified"):
        guard.assert_confirmatory_recorded(repo)


def test_guard_refuses_attempt_record(repo):
    _write(repo, guard.RESULT_HEADING + ": attempt failed")
    _commit(repo)
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="attempt"):
        guard.assert_confirmatory_recorded(repo)


def test_guard_passes_on_committed_result(repo):
    _write(repo, guard.RESULT_HEADING)
    _commit(repo)
    guard.assert_confirmatory_recorded(repo)


def test_guard_passes_on_this_repo():
    guard.assert_confirmatory_recorded()


def test_guard_refuses_a_later_committed_edit(repo):
    _write(repo, guard.RESULT_HEADING)
    _commit(repo)
    (repo / MD).write_text(f"{guard.RESULT_HEADING}\n\nedited and committed\n")
    _git(repo, "add", MD)
    _git(repo, "commit", "-q", "-m", "edit the record")
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="pinned"):
        guard.assert_confirmatory_recorded(repo)


# --- no .git (a replication archive): the record's bytes are checked against the pinned blobs


def _copy_real_record(dest: Path) -> None:
    from aideleg.config import ROOT

    for rel in guard.CONFIRMATORY:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        (dest / rel).write_bytes((ROOT / rel).read_bytes())


def test_blob_sha1_equals_git_hash_object(tmp_path: Path):
    p = tmp_path / "f.txt"
    p.write_bytes(b"some bytes\n")
    want = subprocess.run(["git", "hash-object", str(p)], capture_output=True, text=True,
                          check=True).stdout.strip()
    assert guard.blob_sha1(p.read_bytes()) == want


def test_guard_without_git_passes_on_the_real_bytes(tmp_path: Path):
    _copy_real_record(tmp_path)
    assert not (tmp_path / ".git").exists()
    guard.assert_confirmatory_recorded(tmp_path)


def test_guard_without_git_refuses_edited_bytes(tmp_path: Path):
    _copy_real_record(tmp_path)
    md = tmp_path / MD
    md.write_bytes(md.read_bytes() + b"\nedited\n")
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="pinned"):
        guard.assert_confirmatory_recorded(tmp_path)


def test_guard_without_git_refuses_a_missing_file(tmp_path: Path):
    _copy_real_record(tmp_path)
    (tmp_path / ATTEMPT).unlink()
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="not present"):
        guard.assert_confirmatory_recorded(tmp_path)


def test_guard_without_git_still_refuses_an_attempt_record(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(guard, "PINNED", dict(guard.PINNED))
    _write(tmp_path, guard.RESULT_HEADING + ": attempt failed")
    guard.PINNED.update({rel: guard.blob_sha1((tmp_path / rel).read_bytes())
                         for rel in guard.CONFIRMATORY})
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="attempt"):
        guard.assert_confirmatory_recorded(tmp_path)


def test_guard_with_git_ignores_the_fallback(repo):
    """With .git present, the real bytes untracked are still refused: git governs."""
    _copy_real_record(repo)
    with pytest.raises(guard.ConfirmatoryNotRecorded, match="not committed"):
        guard.assert_confirmatory_recorded(repo)
