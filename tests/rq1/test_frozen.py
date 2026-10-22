"""The frozen-code guard of P-RQ1 (PAP §0.5): after the first real run, the bound RQ1 code and
the numerical library versions must stay as that run recorded them."""

import importlib.metadata
import json
import subprocess

import pytest

from aideleg.config import ROOT

RESULT = ROOT / "docs/results/rq1/confirmatory_rq1.json"
PACKAGES = ("numpy", "scipy", "polars", "statsmodels")
MESSAGE = "bound RQ1 code changed after the P-RQ1 first run: record a §11 deviation (PAP §0.5)"


def _meta() -> dict:
    if not RESULT.exists():
        pytest.skip("no P-RQ1 first run yet")
    meta = json.loads(RESULT.read_text(encoding="utf-8"))["meta"]
    if meta.get("scrambled", True):
        pytest.skip("the result file is a scrambled dry run")
    return meta


def test_bound_code_unchanged_since_first_run():
    meta = _meta()
    changed = []
    for path, blob in meta["blobs"].items():
        now = subprocess.run(["git", "-C", str(ROOT), "hash-object", path], capture_output=True,
                             text=True).stdout.strip()
        if now != blob:
            changed.append(f"{path}: {blob} -> {now or 'missing'}")
    for pkg in PACKAGES:
        now = importlib.metadata.version(pkg)
        if now != meta["versions"][pkg]:
            changed.append(f"{pkg}: {meta['versions'][pkg]} -> {now}")
    assert not changed, f"{MESSAGE}: {'; '.join(changed)}"
