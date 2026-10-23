"""The PAP §8.2 robustness rows R1–R38, each covered exactly once.

R12 and R13 are reported by the confirmatory script (`confirm_h5`, run once by Plan 3) in
`docs/results/confirmatory_h5.md`; every other row is Plan 4's, written by the task(s) listed.
No Plan 2 or Plan 3 output reports a §8.2 row (checked in Plan 4 Task 1).
"""

from dataclasses import dataclass
from typing import Literal

Owner = Literal["plan4", "confirmatory_script"]

OUT_DIR = "docs/results/robustness"
H5_RECORD = "docs/results/confirmatory_h5.md"


@dataclass(frozen=True)
class Row:
    id: str
    owner: Owner
    task: tuple[int, ...]
    applies_to: tuple[str, ...]
    outputs: tuple[str, ...]


def output_stem(row_id: str) -> str:
    """ "R5" -> "R05": the file stem of a row's outputs, so files sort in row order."""
    return f"R{int(row_id.removeprefix('R')):02d}"


def _plan4(row_id: str, task: tuple[int, ...], applies_to: tuple[str, ...]) -> Row:
    stem = output_stem(row_id)
    return Row(row_id, "plan4", task, applies_to, (f"{OUT_DIR}/{stem}.csv", f"{OUT_DIR}/{stem}.md"))


def _script(row_id: str, applies_to: tuple[str, ...]) -> Row:
    return Row(row_id, "confirmatory_script", (), applies_to, (H5_RECORD,))


_H5 = ("H5", "H5b")
_H5_RQ2 = ("H5", "H5b", "RQ2")

ROWS: dict[str, Row] = {
    r.id: r
    for r in (
        _plan4("R1", (7,), ("RQ2", "H5", "H5b")),
        _plan4("R2", (7,), _H5_RQ2),
        _plan4("R3", (7,), _H5_RQ2),
        _plan4("R4", (10,), ("A_pooled",)),
        _plan4("R5", (8,), _H5),
        _plan4("R6", (9,), _H5),
        _plan4("R7", (8,), _H5),
        _plan4("R8", (10,), ("Design A",)),
        _plan4("R9", (10,), ("event studies",)),
        _plan4("R10", (8, 11), ("H1", "H3", "H5", "H5b")),
        _plan4("R11", (7,), _H5_RQ2),
        _script("R12", _H5),
        _script("R13", _H5),
        _plan4("R14", (7,), ("H5b", "RQ2")),
        _plan4("R15", (7,), _H5_RQ2),
        _plan4("R16", (10,), ("A_pooled", "r6 descriptives")),
        _plan4("R17", (7,), ("RQ2",)),
        _plan4("R18", (8,), _H5),
        _plan4("R19", (8,), _H5),
        _plan4("R20", (7,), _H5_RQ2),
        _plan4("R21", (8,), _H5),
        _plan4("R22", (12,), ("H2",)),
        _plan4("R23", (11, 12), ("H1", "H2")),
        _plan4("R24", (11,), ("H1", "H3")),
        _plan4("R25", (13,), ("H1", "H4")),
        _plan4("R26", (11,), ("H1", "H3")),
        _plan4("R27", (11,), ("H3",)),
        _plan4("R28", (13,), ("H4",)),
        _plan4("R29", (14,), ("H6",)),
        _plan4("R30", (14,), ("H6",)),
        _plan4("R31", (11,), ("H3",)),
        _plan4("R32", (9,), _H5),
        _plan4("R33", (7,), _H5_RQ2),
        _plan4("R34", (8,), _H5),
        _plan4("R35", (8,), _H5),
        _plan4("R36", (12,), ("H2",)),
        _plan4("R37", (12,), ("H2",)),
        _plan4("R38", (11,), ("H1", "H3")),
    )
}
