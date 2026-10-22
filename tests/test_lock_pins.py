"""Plan 2 may add dependencies, but the numerical core must stay at its pap-v1 versions."""

import subprocess
import tomllib
from pathlib import Path

from aideleg.config import ROOT

CORE = ("numpy", "scipy", "pandas", "polars", "statsmodels")


def locked_versions(text: str) -> dict[str, str]:
    """name -> version for every [[package]] in a uv.lock."""
    return {p["name"]: p["version"] for p in tomllib.loads(text)["package"]}


def test_locked_versions_parses_package_tables():
    text = '[[package]]\nname = "a"\nversion = "1.0"\n\n[[package]]\nname = "b"\nversion = "2.0"\n'
    assert locked_versions(text) == {"a": "1.0", "b": "2.0"}


def test_core_numeric_versions_unchanged_since_pap_v1():
    now = locked_versions(Path(ROOT / "uv.lock").read_text())
    tagged = locked_versions(
        subprocess.run(["git", "-C", str(ROOT), "show", "pap-v1:uv.lock"],
                       capture_output=True, text=True, check=True).stdout
    )
    for p in CORE:
        assert now[p] == tagged[p], f"{p}: {now[p]} != {tagged[p]} at pap-v1"
