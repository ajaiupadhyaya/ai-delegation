"""The H6 CLI: `all` never acquires; `make h6` is offline, `make h6-data` acquires (C-43)."""

import shutil
import subprocess

import pytest

import aideleg.h6.__main__ as cli
from aideleg.acquire import fetch
from aideleg.config import ROOT
from aideleg.h6 import edgar


def test_all_never_acquires(monkeypatch):
    def fail(*a, **k):
        pytest.fail("network access from `all`")

    monkeypatch.setattr(fetch, "fetch", fail)
    monkeypatch.setattr(fetch, "download", fail)
    monkeypatch.setattr(edgar, "_get_json", fail)
    calls: list[str] = []
    for name in ("build", "talk", "secondary", "summary"):
        monkeypatch.setattr(cli, name, lambda *a, _n=name, **k: calls.append(_n))
    monkeypatch.setattr(cli, "acquire", fail)
    assert cli.main(["all"]) == 0
    assert calls == ["build", "talk", "secondary", "summary"]


def test_build_flags_select_parts(monkeypatch):
    seen: list[tuple] = []
    monkeypatch.setattr(cli, "build", lambda filers, fts: seen.append((filers, fts)))
    cli.main(["build"])
    cli.main(["build", "--fts"])
    cli.main(["build", "--filers"])
    assert seen == [(True, True), (False, True), (True, False)]


def test_acquire_flags_select_parts(monkeypatch):
    seen: list[tuple] = []
    monkeypatch.setattr(cli, "acquire", lambda filers, fts, docs: seen.append((filers, fts, docs)))
    cli.main(["acquire"])
    cli.main(["acquire", "--fts"])
    assert seen == [(True, True, True), (False, True, False)]


@pytest.mark.skipif(shutil.which("make") is None, reason="make not installed")
def test_make_h6_is_offline():
    def dry(target: str) -> str:
        return subprocess.run(
            ["make", "-n", target], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout

    h6 = dry("h6")
    assert "aideleg.h6 all" in h6 and "acquire" not in h6
    assert "aideleg.h6 acquire" in dry("h6-data")
