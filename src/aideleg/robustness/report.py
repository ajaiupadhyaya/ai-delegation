"""The shared record schema, row writer and number formatting of the robustness rows.

Every row writes `docs/results/robustness/R<nn>.csv` (full precision) and `.md` (formatted by
the Global Constraints rules: pp and RQ1 coefficients to 2 decimals, correlations to 3, p to 3
with p < 0.001 shown as "< 0.001"). A row is reported as robustness; it is not a confirmatory
decision (PAP §8.1). `WORDING` (through the adapter) is the last line of every `.md`.
"""

import math
import re
from pathlib import Path

import polars as pl

from aideleg.config import ROOT
from aideleg.results.common import check_text, write_csv
from aideleg.robustness import registry, upstream

ROBUSTNESS_COLUMNS = [
    "row_id",
    "part",
    "variant",
    "applies_to",
    "label",
    "estimand",
    "unit",
    "estimate",
    "scale",
    "ci_lo",
    "ci_hi",
    "stat",
    "p",
    "null",
    "crit_0025",
    "crit_005",
    "n",
    "n_dropped",
    "dropped",
    "note",
]
OUT_DIR = ROOT / registry.OUT_DIR
MARKET_UNIT = "pp of annualised alpha per 1 SD"
RHO_UNIT = "correlation"
NOT_A_DECISION = "reported as robustness; not a confirmatory decision (PAP §8.1)"
_DASH = "—"
_C_NUMBER = re.compile(r"\bC-\d+\b")


def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))


def fmt_pp(x: float) -> str:
    """pp and RQ1 coefficients: 2 decimals."""
    if _missing(x):
        return _DASH
    out = f"{x:.2f}"
    return "0.00" if out == "-0.00" else out


def fmt_crit(x: float) -> str:
    """Critical values: 4 decimals, as `confirmatory_h5.md` prints them."""
    return _DASH if _missing(x) else f"{x:.4f}"


def fmt_rho(r: float) -> str:
    """Correlations: 3 decimals."""
    return _DASH if _missing(r) else f"{r:.3f}"


def fmt_p(p: float) -> str:
    """p-values: 3 decimals, and "< 0.001" below 0.001."""
    if _missing(p):
        return _DASH
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def fmt_stat(x: float) -> str:
    """Test statistics and criticals: 3 decimals (as the confirmatory record prints T)."""
    return _DASH if _missing(x) else f"{x:.3f}"


def check_record(rec: dict) -> None:
    keys = set(rec)
    want = set(ROBUSTNESS_COLUMNS)
    if keys != want:
        raise ValueError(
            f"record keys differ from ROBUSTNESS_COLUMNS: missing "
            f"{sorted(want - keys)}, extra {sorted(keys - want)}"
        )


def _table(records: list[dict]) -> list[str]:
    head = [
        "part",
        "applies to",
        "estimate",
        "scale",
        "interval",
        "stat",
        "p",
        "null",
        "c_0.025",
        "c_0.05",
        "n",
        "dropped",
        "note",
    ]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in records:
        num = fmt_rho if r["unit"] == RHO_UNIT else fmt_pp
        ci = (
            _DASH
            if _missing(r["ci_lo"]) and _missing(r["ci_hi"])
            else f"[{num(r['ci_lo'])}, {num(r['ci_hi'])}]"
        )
        cells = [
            r["part"],
            r["applies_to"],
            num(r["estimate"]),
            num(r["scale"]),
            ci,
            fmt_stat(r["stat"]),
            fmt_p(r["p"]),
            r["null"] or _DASH,
            fmt_crit(r["crit_0025"]),
            fmt_crit(r["crit_005"]),
            _DASH if _missing(r["n"]) else str(r["n"]),
            r["dropped"] or "none",
            r["note"] or "",
        ]
        lines.append("| " + " | ".join(str(c) for c in cells) + " |")
    return lines


def write_row(
    row_id: str, records: list[dict], notes: list[str], *, out_dir: Path | None = None
) -> tuple[Path, Path]:
    """Write `R<nn>.csv` and `R<nn>.md` for a Plan 4 row of the registry. Refuses a record
    whose keys differ from `ROBUSTNESS_COLUMNS`, an empty record list and an unknown row."""
    if row_id not in registry.ROWS or registry.ROWS[row_id].owner != "plan4":
        raise ValueError(f"{row_id} is not a Plan 4 row of the PAP §8.2 registry")
    if not records:
        raise ValueError(f"{row_id}: no records")
    for rec in records:
        check_record(rec)
    for n in [*notes, *(r["note"] or "" for r in records)]:
        if "[default]" in n and not _C_NUMBER.search(n):
            raise ValueError(f"{row_id}: a [default] note names no §11 C- number: {n!r}")
    out_dir = OUT_DIR if out_dir is None else Path(out_dir)
    stem = registry.output_stem(row_id)
    labels = sorted({r["label"] for r in records})
    units = sorted({r["unit"] for r in records if r["unit"]})
    lines = [
        f"# {row_id}: robustness row (PAP §8.2 {row_id})",
        "",
        f"Source: PAP §8.2, row {row_id}. Label: {', '.join(labels)}.",
        "",
        f"Every record below is {NOT_A_DECISION}.",
        "",
        f"Units: {'; '.join(units) or 'none'}. Estimates and scales are formatted to 2 decimals "
        "(correlations to 3), p to 3 decimals; the CSV keeps full precision.",
    ]
    if notes:
        lines += ["", "## Notes", "", *[f"- {n}" for n in notes]]
    lines += ["", "## Results", "", *_table(records), "", upstream.WORDING, ""]
    text = "\n".join(lines)
    check_text(text)
    csv_path, md_path = out_dir / f"{stem}.csv", out_dir / f"{stem}.md"
    df = pl.DataFrame(
        [{k: r[k] for k in ROBUSTNESS_COLUMNS} for r in records], infer_schema_length=None
    )
    write_csv(df.select(ROBUSTNESS_COLUMNS), csv_path)
    md_path.write_text(text, encoding="utf-8")
    return csv_path, md_path
