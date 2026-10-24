"""The robustness appendix (Plan 4 Task 15): the coverage gate, `summary.md` and
`implementation_choices.md`.

`summary.md` is one table: each row's records beside the primary's estimate, read from the
committed confirmatory and generated result files (nothing is re-estimated). It states no verdict
and counts nothing (PAP §8.1). `implementation_choices.md` collects every **[default]** note of
the row files with its §11 C-entry.

AEI data are conversations matched to O*NET tasks.
"""

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import polars as pl

from aideleg import paplog
from aideleg.config import ROOT
from aideleg.results.common import check_text, generated_line
from aideleg.robustness import registry, report, rows, upstream

GENERATOR = "uv run python -m aideleg.robustness --summary"
SUMMARY = "summary.md"
CHOICES = "implementation_choices.md"
SUMMARY_COLUMNS = (
    "row",
    "applies to",
    "label",
    "PAP source",
    "part",
    "estimand",
    "variant",
    "primary",
    "file",
)
# PAP §8.2's own words for the two rows the confirmatory script reports.
SCRIPT_LABELS = {"R12": "co-primary reporting", "R13": "co-primary reporting; co-condition"}
_SCRIPT_SPECS = {"R12": "R12 (ranks)", "R13": "R13 (drop Softw)"}

INTERVAL_STATEMENT = (
    "Every market interval of the robustness rows (H5, H5b and the H6 gap–return slope) is the "
    "c_0.05 interval b̂ ± c_0.05·s, with s and c recomputed for the row (R35: its own scale and "
    "t₂₁ critical, PAP §11 C-75); P14 also defines the c_0.025 interval b̂ ± c_0.025·s, which "
    "the row files do not print (both criticals are in each market record)."
)
P14_STATEMENT = (
    "Any prose that calls a market robustness result a non-rejection uses the fixed P14 wording "
    "of `docs/results/confirmatory_h5.md` verbatim (PAP §3.3 P14)."
)
NOT_A_DECISION = (
    "Every row is reported whatever its result. No row changes a confirmatory decision (R13 is "
    "the confirmatory script's co-condition, reported in `confirmatory_h5.md`), no row carries "
    "error control across rows, and rows are not summarised by counting (PAP §8.1)."
)

_RQ1_JSON = upstream.RQ1_DIR / "confirmatory_rq1.json"
_RQ2_CSV = upstream.RQ2_DIR / "could_vs_does.csv"
_ANATOMY_CSV = upstream.RQ1_DIR / "anatomy_wage_decile.csv"
_H5_MD = ROOT / registry.H5_RECORD
_RQ1_UNITS = {
    "H1": rows._PP_UNITS,
    "H3": rows._PP_UNITS,
    "H4": rows._PP_UNITS,
    "H2": "pp of the outcome share per year",
}
# A variant estimand that replaces the primary's coefficient: R27's continuous Consequence of
# Error (D15) in place of the error-cost indicator; the H2 slope's record name.
_RQ1_ALIAS = {("H3", "coe"): "error_cost", ("H2", "beta (pp per year)"): "trend"}
_DESIGN_A_PARTS = ("terciles", "fm", "events")
_DASH = "—"


@dataclass(frozen=True)
class Primary:
    est: float
    lo: float | None
    hi: float | None
    text: str
    quoted: bool = False  # True when quoted at a result document's printed precision


# --- coverage gate ----------------------------------------------------------------------------


def _header(path: Path) -> str:
    """A result file's header: the first Markdown heading of a `.md`, the first line of a
    `.csv`."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return ""
    if path.suffix == ".csv":
        return lines[0] if lines else ""
    return next((ln for ln in lines if ln.startswith("#")), "")


def _names(text: str, rid: str) -> bool:
    n = int(rid.removeprefix("R"))
    return re.search(rf"\bR0?{n}\b", text) is not None


# Result files whose header names an R-ID that is not a §8.2 row: the RQ2 title "widths of
# the R7 bounds" names the D1 suppression bounds (PAP §8.2 R10's "R7 bounds"), not row R7.
COVERAGE_EXEMPT = {"docs/results/rq2/bounds.md": "R7 here is the D1 suppression bounds"}


def coverage(root: Path = ROOT) -> dict[str, list[str]]:
    """For each §8.2 row, the files that report it: the owner's outputs (Plan 4's `R<nn>.csv`
    and `.md` both present, or the confirmatory record naming the row), plus any other result
    file under `docs/results` whose header names the row ID (except `COVERAGE_EXEMPT`).
    Exactly one entry is the gate."""
    root = Path(root)
    results = root / "docs/results"
    own = {root / o for r in registry.ROWS.values() for o in r.outputs}
    others = [
        p
        for p in sorted(results.rglob("*"))
        if p.suffix in (".md", ".csv")
        and p.is_file()
        and p not in own
        and str(p.relative_to(root)) not in COVERAGE_EXEMPT
    ]
    headers = {p: _header(p) for p in others}
    out: dict[str, list[str]] = {}
    for rid, row in registry.ROWS.items():
        found: list[str] = []
        if row.owner == "plan4":
            if all((root / o).exists() for o in row.outputs):
                found.append(row.outputs[0])
        else:
            h5 = root / registry.H5_RECORD
            if h5.exists() and _names(h5.read_text(encoding="utf-8"), rid):
                found.append(registry.H5_RECORD)
        found += [str(p.relative_to(root)) for p, h in headers.items() if _names(h, rid)]
        out[rid] = found
    return out


# --- PAP §8.2 sources -------------------------------------------------------------------------


def pap_sources(pap: Path = paplog.PAP) -> dict[str, str]:
    """The Source column of the PAP §8.2 table, by row ID."""
    text = Path(pap).read_text(encoding="utf-8")
    body = text.split("### 8.2 The list", 1)[1].split("\n### ", 1)[0]
    out = {}
    for ln in body.splitlines():
        m = re.match(r"^\| (R\d+) \|", ln)
        if m:
            out[m[1]] = ln.rstrip().rstrip("|").rsplit("|", 1)[1].strip()
    return out


# --- records and primaries --------------------------------------------------------------------

_NUMERIC = ("estimate", "scale", "ci_lo", "ci_hi", "stat", "p", "crit_0025", "crit_005")


def load_records(out_dir: Path = report.OUT_DIR) -> pl.DataFrame:
    """Every Plan 4 row's records, in registry order, numeric columns at full precision."""
    frames = []
    for row in registry.ROWS.values():
        if row.owner != "plan4":
            continue
        df = pl.read_csv(Path(out_dir) / Path(row.outputs[0]).name, infer_schema_length=0)
        frames.append(df.select(report.ROBUSTNESS_COLUMNS))
    return pl.concat(frames).with_columns(pl.col(c).cast(pl.Float64) for c in _NUMERIC)


def _num(s: str) -> float:
    return float(s.replace("−", "-"))


@cache
def h5_record() -> dict[str, tuple[str, str, str]]:
    """From `confirmatory_h5.md`, as printed: b and its c_0.05 interval for H5 and H5b, and b
    for the R12/R13 specifications (keys `H5`, `H5b`, `H5 R12 (ranks)`, ...)."""
    text = _H5_MD.read_text(encoding="utf-8")
    out: dict[str, tuple[str, str, str]] = {}
    for ln in text.splitlines():
        m = re.match(r"^\| (H5b?(?: R1[23] \([^)]*\))?) \| (-?\d+\.\d+) \|", ln)
        if m:
            out[m[1]] = (m[2], "", "")
    for h in ("H5", "H5b"):
        sec = text.split(f"- **{h}.**", 1)[1]
        m = re.search(r"c_0\.05 x s: \[(-?\d+\.\d+), (-?\d+\.\d+)\]", sec)
        out[h] = (out[h][0], m[1], m[2])
    return out


def _quoted(b: str, lo: str = "", hi: str = "") -> Primary:
    return Primary(_num(b), _num(lo) if lo else None, _num(hi) if hi else None, b, quoted=True)


def _fmt(unit: str | None, x: float) -> str:
    return report.fmt_rho(x) if unit == report.RHO_UNIT else report.fmt_pp(x)


def _primary(unit: str | None, est: float, lo, hi) -> Primary:
    return Primary(est, lo, hi, _fmt(unit, est))


@cache
def _rq1() -> dict:
    return json.loads(_RQ1_JSON.read_text(encoding="utf-8"))["results"]


@cache
def _rq2() -> dict[tuple[str, str], tuple[float, float, float]]:
    df = pl.read_csv(_RQ2_CSV)
    return {
        (r["design"], f"spearman {r['benchmark']} vs {r['aei']}"): (
            r["spearman"],
            r["ci_low"],
            r["ci_high"],
        )
        for r in df.iter_rows(named=True)
    }


@cache
def _design_a() -> dict[tuple[str, str], dict]:
    """Plan 3's committed primary terciles, Fama–MacBeth and event-study rows, mapped to
    records by the same builders the rows use, keyed by (part, estimand)."""
    d = upstream.RQ3_DIR
    recs = (
        rows._tercile_records("R4", pl.read_csv(d / "terciles.csv"), "primary")
        + rows._fm_records("R4", pl.read_csv(d / "fama_macbeth.csv"), "primary")
        + rows._event_records(
            "R4", "events", pl.read_csv(d / "event_study.csv", infer_schema_length=None), "primary"
        )
    )
    return {(r["part"], r["estimand"]): r for r in recs}


@cache
def _anatomy() -> dict[str, dict]:
    df = pl.read_csv(_ANATOMY_CSV, infer_schema_length=None)
    return {
        ("no wage" if r["decile"] is None else str(r["decile"])): r
        for r in df.iter_rows(named=True)
    }


@cache
def _h6() -> dict[str, Primary]:
    gap = (upstream.H6_DIR / "gap.md").read_text(encoding="utf-8")
    m = re.search(r"^\| (-?\d+\.\d+) \| \[(-?\d+\.\d+), (-?\d+\.\d+)\] \|", gap, flags=re.M)
    ret = (upstream.H6_DIR / "gap_returns.md").read_text(encoding="utf-8")
    b = re.search(r"^\| b \(pp[^|]*\| (-?\d+\.\d+) \|", ret, flags=re.M)
    ci = re.search(r"^\| 95% CI for b[^|]*\| \[(-?\d+\.\d+), (-?\d+\.\d+)\] \|", ret, flags=re.M)
    return {
        "H6 divergence": _quoted(m[1], m[2], m[3]),
        "H6 gap-return": _quoted(b[1], ci[1], ci[2]),
    }


def record_outcome(rec: dict) -> str:
    """An RQ1 record's outcome: the `outcome=` field of its variant, or, for a row that states
    none (R25 re-tests the committed fits, R28 varies the H4 sample), the primary's."""
    m = re.search(r"(?:^|; )outcome=([^;]+)", rec["variant"] or "")
    return m[1].strip() if m else _rq1()[rec["applies_to"]]["outcome"]


def primary_for(rec: dict) -> Primary | None:
    """The primary estimate a record stands beside, from the committed result files, or None
    when the record has no primary counterpart (placebo dates, the A_pooled index comparison,
    a coefficient the primary does not estimate, another outcome or outcome units)."""
    unit, applies, est, part = rec["unit"], rec["applies_to"], rec["estimand"], rec["part"]
    if unit == report.MARKET_UNIT and applies in ("H5", "H5b"):
        return _quoted(*h5_record()[applies])
    if applies in _RQ1_UNITS:
        if unit != _RQ1_UNITS[applies] or record_outcome(rec) != _rq1()[applies]["outcome"]:
            return None
        name = _RQ1_ALIAS.get((applies, est), est)
        c = _rq1()[applies]["coefs"].get(name)
        return None if c is None else _primary(unit, c["estimate"], c["ci_low"], c["ci_high"])
    if part == "rq2":
        design = "A_pooled" if "A_pooled" in registry.ROWS[rec["row_id"]].applies_to else "B"
        v = _rq2().get((design, est))
        return None if v is None else _primary(unit, *v)
    if part in _DESIGN_A_PARTS:
        r = _design_a().get((part, est))
        return None if r is None else _primary(unit, r["estimate"], r["ci_lo"], r["ci_hi"])
    if part == "r6_descriptives":
        words = est.split()
        row = _anatomy().get(" ".join(words[3:-1]))
        v = None if row is None else row.get(words[-1])
        return None if v is None else _primary(unit, v, None, None)
    if applies in ("H6 divergence", "H6 gap-return"):
        return _h6()[applies]
    return None


# --- summary.md -------------------------------------------------------------------------------


def _display(unit: str | None, prim: Primary) -> str:
    """The primary at the row files' precision (pp 2 decimals, correlations 3). A value quoted
    at 3 decimals is rounded once more only when that rounding is not a tie."""
    if prim.quoted and unit != report.RHO_UNIT:
        digits = prim.text.lstrip("-").split(".")[1]
        if len(digits) > 2 and digits[2:] == "5" + "0" * (len(digits) - 3):
            raise ValueError(f"ambiguous rounding of the quoted primary {prim.text}")
    return _fmt(unit, prim.est)


def _link(rid: str) -> str:
    if registry.ROWS[rid].owner == "confirmatory_script":
        return "[confirmatory_h5.md](../confirmatory_h5.md)"
    stem = registry.output_stem(rid)
    return f"[{stem}.md]({stem}.md)"


def _cells(*cells: str) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def summary_lines(records: pl.DataFrame) -> list[str]:
    """The summary table body, in registry order. A record with a primary counterpart gets its
    own line; the records of a (row, part, applies to) group with none get one line that points
    to the row file. Records without an estimate (joint p-values) are in the row files only."""
    src = pap_sources()
    lines = [_cells(*SUMMARY_COLUMNS), "|" + "---|" * len(SUMMARY_COLUMNS)]
    h5 = h5_record()
    for rid, row in registry.ROWS.items():
        if row.owner == "confirmatory_script":
            for h in row.applies_to:
                prim = h5[h][0]
                var = h5[f"{h} {_SCRIPT_SPECS[rid]}"][0]
                lines.append(
                    _cells(
                        rid,
                        h,
                        SCRIPT_LABELS[rid],
                        src[rid],
                        "confirmatory script",
                        f"{h} b, {_SCRIPT_SPECS[rid]}",
                        var,
                        prim,
                        _link(rid),
                    )
                )
            continue
        sub = records.filter(pl.col("row_id") == rid, pl.col("estimate").is_not_null())
        groups: dict[tuple[str, str], list[dict]] = {}
        for r in sub.iter_rows(named=True):
            groups.setdefault((r["part"], r["applies_to"]), []).append(r)
        for (part, applies), recs in groups.items():
            unmatched: list[dict] = []
            for r in recs:
                prim = primary_for(r)
                if prim is None:
                    unmatched.append(r)
                    continue
                lines.append(
                    _cells(
                        rid,
                        applies,
                        r["label"],
                        src[rid],
                        part,
                        r["estimand"],
                        _fmt(r["unit"], r["estimate"]),
                        _display(r["unit"], prim),
                        _link(rid),
                    )
                )
            if unmatched:
                labels = "; ".join(dict.fromkeys(r["label"] for r in unmatched))
                lines.append(
                    _cells(
                        rid,
                        applies,
                        labels,
                        src[rid],
                        part,
                        "records without a primary counterpart (in the row file)",
                        "see file",
                        _DASH,
                        _link(rid),
                    )
                )
    return lines


def summary_text(records: pl.DataFrame) -> str:
    lines = [
        "# Robustness appendix: summary (PAP §8.2)",
        "",
        generated_line(GENERATOR),
        "",
        NOT_A_DECISION,
        "",
        INTERVAL_STATEMENT,
        "",
        P14_STATEMENT,
        "",
        "Each line puts a row's estimate beside the primary's, both formatted as in the row files "
        "(pp and RQ1 coefficients to 2 decimals, correlations to 3); the R12 and R13 lines quote "
        "`confirmatory_h5.md` at its printed precision. Primaries are read from the committed "
        "files: H5 and H5b from `confirmatory_h5.md` and the H6 rows from `h6/gap.md` and "
        "`h6/gap_returns.md` (as printed, then formatted); RQ1 from "
        "`rq1/confirmatory_rq1.json`, only for records with the primary's outcome and units; "
        "RQ2 from `rq2/could_vs_does.csv` (Design B, or A_pooled "
        "for the A_pooled rows); Design A from `rq3/terciles.csv`, `rq3/fama_macbeth.csv` and "
        "`rq3/event_study.csv`; the r6 descriptives from `rq1/anatomy_wage_decile.csv`. "
        "Intervals, statistics, p-values and notes are in the row files. Implementation choices "
        f"where the PAP is silent are listed in [{CHOICES}]({CHOICES}).",
        "",
        *summary_lines(records),
        "",
        upstream.WORDING,
        "",
    ]
    text = "\n".join(lines)
    check_text(text)
    return text


# --- implementation_choices.md ----------------------------------------------------------------


def _default_notes_of(text: str) -> list[str]:
    out: list[str] = []
    in_notes = False
    for ln in text.splitlines():
        if ln.startswith("## "):
            in_notes = ln == "## Notes"
            continue
        if in_notes and ln.startswith("- ") and "[default]" in ln:
            out.append(ln[2:])
        elif ln.startswith("| ") and "[default]" in ln:
            cell = ln.rstrip().rstrip("|").rsplit("|", 1)[1].strip()
            out.append(
                cell[cell.index("[default]") - 2 :]
                if cell.find("**[default]") >= 0
                else cell[cell.index("[default]") :]
            )
    return list(dict.fromkeys(out))


def default_notes(out_dir: Path = report.OUT_DIR) -> list[tuple[str, str]]:
    """(row ID, note) for every **[default]** note of the Plan 4 row files, in registry order."""
    out = []
    for rid, row in registry.ROWS.items():
        if row.owner == "plan4":
            md = Path(out_dir) / Path(row.outputs[1]).name
            out += [(rid, n) for n in _default_notes_of(md.read_text(encoding="utf-8"))]
    return out


def _entry_titles(kinds: Iterable[str] = ("C", "D")) -> dict[tuple[str, int], str]:
    return {(e["kind"], e["n"]): e["title"] for e in paplog.entries() if e["kind"] in kinds}


def choices_text(notes: list[tuple[str, str]]) -> str:
    titles = _entry_titles()
    lines = [
        "# Implementation choices where the PAP is silent",
        "",
        generated_line(GENERATOR),
        "",
        "Every **[default]** note of the robustness row files, as the row file prints it, with "
        "the PAP §11 clarification(s) it names. Each was fixed and logged before the row's "
        "first robustness read unless its §11 entry says otherwise.",
        "",
        INTERVAL_STATEMENT,
        "",
        P14_STATEMENT,
    ]
    current = None
    for rid, note in notes:
        if rid != current:
            lines += [
                "",
                f"## {rid} ([{registry.output_stem(rid)}.md]({registry.output_stem(rid)}.md))",
                "",
            ]
            current = rid
        cs = list(dict.fromkeys(int(c) for c in re.findall(r"\bC-(\d+)\b", note)))
        if not cs:
            raise ValueError(f"{rid}: a [default] note names no §11 C- number: {note!r}")
        refs = "; ".join(f"C-{c} ({titles[('C', c)]})" for c in cs)
        lines.append(f"- {note} — §11 {refs}.")
    lines += [
        "",
        "## Reproduction of the row files",
        "",
        f"- §11 C-80 ({titles[('C', 80)]}): a re-run must reproduce every row `.md` byte for "
        "byte; a regenerated CSV reproduces the committed one when every non-numeric cell is "
        "identical and every numeric cell agrees within relative 1e-9 (absolute 1e-12 near "
        "zero), and the committed bytes are then kept (`reproduce.csv_equivalent`, used by "
        "`report.write_row`). The last float digits of R15, R28 and R29 move from run to run "
        "(summation order); no printed number moves.",
        "",
        "## Approved deviation affecting code the robustness rows call",
        "",
        f"- D-2 ({titles[('D', 2)]}): approved by Ajai on 2026-10-23. Plan 3's "
        "`h6.edgar.hits_from_saved(phrases=None)` now filters to `fts_phrases()`, as its "
        "docstring says; the primary H6 outputs are byte-identical. R29 and R30 pass their "
        "phrase lists explicitly, so no robustness number changed by it.",
        "",
        upstream.WORDING,
        "",
    ]
    text = "\n".join(lines)
    check_text(text)
    return text


def write_appendix(out_dir: Path = report.OUT_DIR) -> tuple[Path, Path]:
    """Write `summary.md` and `implementation_choices.md` from the committed row files."""
    out_dir = Path(out_dir)
    s, c = out_dir / SUMMARY, out_dir / CHOICES
    s.write_text(summary_text(load_records(out_dir)), encoding="utf-8")
    c.write_text(choices_text(default_notes(out_dir)), encoding="utf-8")
    return s, c
