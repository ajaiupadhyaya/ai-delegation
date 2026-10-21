import subprocess
from datetime import date
from pathlib import Path

import pytest

from aideleg.market import seal


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _git(tmp_path, "config", "commit.gpgsign", "false")
    _git(tmp_path, "config", "tag.gpgsign", "false")
    _git(tmp_path, "commit", "-q", "--allow-empty", "-m", "init")
    return tmp_path


def test_sealed_without_tag_raises(repo):
    assert not seal.pap_frozen(repo)
    with pytest.raises(seal.SealedPeriodError):
        seal.assert_unsealed(date(2022, 11, 30), repo=repo)
    seal.assert_unsealed(date(2022, 11, 29), repo=repo)


def test_unsealed_after_tag(repo):
    _git(repo, "tag", "pap-v1")
    assert seal.pap_frozen(repo)
    seal.assert_unsealed(date(2026, 8, 31), repo=repo)


def test_non_git_directory_counts_as_not_frozen(tmp_path):
    assert not seal.pap_frozen(tmp_path / "nowhere")
