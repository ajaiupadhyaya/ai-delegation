"""PAP §11 C-80: when a regenerated robustness CSV reproduces the committed one.

Some rows' last float digits move from run to run (summation order after an unordered polars
`group_by`; R15, R28, R29). A CSV reproduces another when the headers and every non-numeric
cell are identical, and every numeric cell agrees within relative `REL_TOL` (absolute `ABS_TOL`
near zero). A `.md` must still match byte for byte. Task 33's fresh-clone check reuses this.
"""

import csv
import io
import math
from pathlib import Path

REL_TOL = 1e-9
ABS_TOL = 1e-12


def _rows(x: str | bytes | Path) -> list[list[str]]:
    if isinstance(x, Path):
        x = x.read_text(encoding="utf-8")
    elif isinstance(x, bytes):
        x = x.decode("utf-8")
    return list(csv.reader(io.StringIO(x)))


def _float(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def _cell_equivalent(a: str, b: str) -> bool:
    if a == b:
        return True
    x, y = _float(a), _float(b)
    if x is None or y is None:
        return False
    return math.isclose(x, y, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def csv_equivalent(a: str | bytes | Path, b: str | bytes | Path) -> bool:
    """True when CSV `b` reproduces CSV `a` under the C-80 tolerance (text, bytes or a path)."""
    ra, rb = _rows(a), _rows(b)
    if len(ra) != len(rb) or not ra or ra[0] != rb[0]:
        return False
    return all(
        len(x) == len(y) and all(_cell_equivalent(p, q) for p, q in zip(x, y, strict=True))
        for x, y in zip(ra[1:], rb[1:], strict=True)
    )
