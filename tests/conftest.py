"""Shared test setup: the synthetic RQ1 inputs (`tests/rq1/synth.py`) import as `synth` from
any test directory."""

import sys
from pathlib import Path

_RQ1 = str(Path(__file__).resolve().parent / "rq1")
if _RQ1 not in sys.path:
    sys.path.insert(0, _RQ1)
