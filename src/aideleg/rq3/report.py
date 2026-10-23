"""RQ3 markdown helpers and `summary.md` under the D11 framing (PAP §7, D3; spec §6).

`WORDING` and `FORBIDDEN_PHRASES` come from Plan 2 (`aideleg.results.common`); this module defines
no disclaimer of its own. The summary carries no exploratory estimate: it quotes the confirmatory
record's fixed wording verbatim, names the record's commit, and indexes the exploratory docs by
title.
"""

import re
import subprocess
from collections.abc import Sequence
from pathlib import Path

import polars as pl

from aideleg.config import ROOT
from aideleg.results.common import FORBIDDEN_PHRASES, WORDING, check_text, generated_line

__all__ = [
    "FORBIDDEN_PHRASES",
    "WORDING",
    "fixed_wording",
    "md_table",
    "write_summary",
    "zero_assigned_bullets",
    "zero_assigned_lines",
]

RECORD = ROOT / "docs/results/confirmatory_h5.md"
TITLE = "RQ3: what the market evidence can and cannot yet say"
GENERATOR = "uv run python -m aideleg.rq3 summary"
PLAUSIBILITY_PP = 5.0  # D11: the plausibility threshold, pp of annualised alpha per 1 SD
_WORDING_PREFIX = "  - Fixed wording:"
_MDE = re.compile(r"departure from H0 of at least ([0-9.]+) pp per 1 SD")
PASSED_EXPO_LINE = (
    "- Zero-assigned employment share (D3): this run used an exposure frame passed "
    "by the caller, which states the share in its own notes."
)
_DECISION = re.compile(r"^- \*\*(H5b?)\.\*\* .*primary rejection: (True|False)", re.M)


def zero_assigned_lines(designs: Sequence[str], zero: pl.DataFrame | None = None) -> list[str]:
    """One D3 line per design, from `zero` (default `data.zero_assigned()`); never typed."""
    if zero is None:
        from aideleg.rq3 import data

        zero = data.zero_assigned()
    out = []
    for d in designs:
        row = zero.filter(pl.col("design") == d)
        if row.height != 1:
            raise ValueError(f"no zero-assigned share for Design {d}")
        out.append(
            f"Zero-assigned employment share, Design {d}: "
            f"{float(row['no_usage_emp_pct'][0]):.2f}% (D3)"
        )
    return out


def zero_assigned_bullets(designs: Sequence[str], zero: pl.DataFrame | None) -> list[str]:
    """The D3 lines as markdown bullets for a generated doc. `zero=None` means the caller passed
    its own exposure frame, so the doc says the caller states the share instead."""
    if zero is None:
        return [PASSED_EXPO_LINE]
    return [f"- {line}" for line in zero_assigned_lines(designs, zero)]


def _cell(v, floats: int) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{floats}f}"
    return str(v)


def md_table(df: pl.DataFrame, floats: int = 3) -> str:
    """A markdown table; floats to `floats` decimals, null as `—`."""
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(_cell(v, floats) for v in row) + " |" for row in df.iter_rows()]
    return "\n".join(lines)


def fixed_wording(text: str) -> list[str]:
    """The `  - Fixed wording:` lines of the confirmatory record, verbatim and in order."""
    return [ln for ln in text.splitlines() if ln.startswith(_WORDING_PREFIX)]


def _record_commit(record: Path = RECORD, repo: Path = ROOT) -> str:
    """The last commit that touched the confirmatory record."""
    out = subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "log",
            "-n1",
            "--format=%H",
            "--",
            str(Path(record).relative_to(repo)),
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not out:
        raise ValueError(f"{record} has no commit")
    return out


def _title(path: Path) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    if not first.startswith("# "):
        raise ValueError(f"{path.name} does not start with a heading")
    return first[2:]


def _summary_text(
    record_text: str, record_rel: str, commit: str, docs: Sequence[Path], has_influence: bool
) -> str:
    wording = fixed_wording(record_text)
    decisions = _DECISION.findall(record_text)
    mde = _MDE.search(wording[0]) if wording else None
    if len(wording) != 2 or len(decisions) != 2 or mde is None:
        raise ValueError(
            "the confirmatory record must carry two fixed-wording lines, two "
            "decisions and the primary MDE"
        )
    primary_mde = float(mde.group(1))
    if not primary_mde > PLAUSIBILITY_PP:
        raise ValueError(
            f"primary MDE {primary_mde} pp does not exceed the D11 threshold "
            f"{PLAUSIBILITY_PP} pp; the D11 framing does not apply"
        )
    plain = [f"- {h}: {'rejected' if r == 'True' else 'not rejected'}." for h, r in decisions]
    lines = [
        f"# {TITLE}",
        "",
        generated_line(GENERATOR),
        "",
        f"The D11 plausibility rule fires: the primary MDE is {primary_mde:.2f} pp per 1 SD of "
        f"exposure, above the {PLAUSIBILITY_PP:.0f} pp threshold (PAP §7). The paper is "
        "therefore led by RQ1–RQ2; RQ3 is reported in full and in second place.",
        "",
        "## Confirmatory (H5, H5b)",
        "",
        f"The single confirmatory run is recorded in `{record_rel}`, committed in `{commit}`. "
        "Its decisions, stated plainly:",
        "",
        *plain,
        "",
        "Its fixed wording, quoted verbatim:",
        "",
        *wording,
        "",
        "Not rejected is not evidence that b = bbar: the test had 80% power only against a "
        "departure from H0 at least as large as the MDE.",
        "",
    ]
    if has_influence:
        lines += [
            "Influence diagnostics for the two confirmatory fits (P11; not part of the "
            "decision): [influence.md](influence.md).",
            "",
        ]
    lines += [
        "## Exploratory (PAP §8.3)",
        "",
        "These docs do not revisit the confirmatory decision. Each states its own "
        "estimates, intervals and nominal p-values; none is repeated here.",
        "",
    ]
    lines += [f"- [{p.name}]({p.name}): {_title(p)}" for p in docs]
    lines += ["", WORDING, ""]
    return "\n".join(lines)


def write_summary(out_dir: Path, *, record: Path = RECORD, commit: str | None = None) -> Path:
    """Write `out_dir/summary.md`. `commit=None` reads it from `git log` for `record`."""
    out_dir = Path(out_dir)
    record = Path(record)
    commit = _record_commit(record) if commit is None else commit
    try:
        record_rel = str(record.relative_to(ROOT))
    except ValueError:
        record_rel = str(record)
    docs = sorted(p for p in out_dir.glob("*.md") if p.name not in ("summary.md", "influence.md"))
    text = _summary_text(
        record.read_text(encoding="utf-8"),
        record_rel,
        commit,
        docs,
        (out_dir / "influence.md").exists(),
    )
    check_text(text)
    path = out_dir / "summary.md"
    path.write_text(text, encoding="utf-8")
    return path
