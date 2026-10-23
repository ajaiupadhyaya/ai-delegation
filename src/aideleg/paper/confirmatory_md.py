"""Parse the committed confirmatory record `docs/results/confirmatory_h5.md` (Plan 4 Task 18).

Every value is returned as the string `confirm_h5._report` printed, so a number quoted from the
record keeps its printed precision. Nothing is recomputed here. An attempt record (heading
`... : attempt failed`) is refused.

AEI data are conversations matched to O*NET tasks.
"""

import re
from pathlib import Path

from aideleg.config import ROOT

PATH = ROOT / "docs/results/confirmatory_h5.md"
HEADING = "# Confirmatory test of H5 and H5b"
FIELDS = ("b", "s", "bbar", "T_zero", "T_bbar", "p_primary", "p_secondary", "c_0025", "c_005")
_NUM = r"(-?\d+(?:\.\d+)?)"
_DECISION = re.compile(
    r"^- \*\*(H5b?)\.\*\* Holm level reached: (\S+); primary rejection: (True|False); "
    r"R13 co-condition met: (True|False)\.$"
)
_CI = re.compile(
    rf"^  - Interval b \+- c_0\.05 x s: \[{_NUM}, {_NUM}\] pp; "
    rf"b \+- c_0\.025 x s: \[{_NUM}, {_NUM}\] pp\.$"
)
_WORDING = re.compile(r"^  - Fixed wording: (.*)$")
_MDE = re.compile(rf"^  - R13 \(Softw dropped\) MDE at Holm level 0\.025: {_NUM} pp;")
_SECONDARY = {
    "ri_h5": re.compile(rf"^- RI, permute z_delegation, H5: p = {_NUM}\.$"),
    "ri_h5b": re.compile(rf"^- RI, permute z_delegation with z_aioe in place, H5b: p = {_NUM} "),
    "fl_h5b": re.compile(rf"^- Freedman-Lane RI \(pivotal t\), H5b: p = {_NUM};"),
    "fl_coef_h5b": re.compile(rf"coefficient-scored on the same draws: p = {_NUM}\.$"),
}
_HC3 = re.compile(
    rf"^- OLS with HC3 SEs: H5 b = {_NUM} pp \(SE {_NUM}\); "
    rf"H5b b = {_NUM} pp \(SE {_NUM}\)\.$"
)
_PROV = {
    "commit": re.compile(r"^- Commit: `([0-9a-f]+|unknown)`; tag `[^`]+` -> `([^`]+)`\.$"),
    "blob": re.compile(r"^- `src/aideleg/confirm_h5\.py` blob: `([^`]+)`\.$"),
    "vector_sha256": re.compile(r"^- Exposure vector SHA-256: `([0-9a-f]+)`"),
    "window": re.compile(
        r"^- Window (\S+ -> \S+); dates read in it (\S+ -> \S+); "
        r"(\d+) factor days\.$"
    ),
    "n": re.compile(r"^- Industries: (\d+); dropped for a missing return: ([^;]+);"),
}


def _one(pattern: re.Pattern, lines: list[str], what: str) -> re.Match:
    found = [m for m in map(pattern.search, lines) if m]
    if len(found) != 1:
        raise ValueError(f"confirmatory record: {len(found)} matches for {what}, expected 1")
    return found[0]


def parse(path: Path = PATH) -> dict[str, dict]:
    """The record as printed strings.

    Keys: every specification label (`"H5"`, `"H5b"`, `"H5 R12 (ranks)"`, ...) with the fields
    `FIELDS`; `"decision"` per hypothesis (`holm_level`, `rejected`, `co_condition`, `ci_005`,
    `ci_0025`, `wording`, `mde_r13`); `"secondary"` (RI p-values, HC3 b and SE);
    `"provenance"` (commit, tag_commit, blob, vector_sha256, window, dates_read, n_days, n,
    dropped)."""
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0] != HEADING:
        first = lines[0] if lines else ""
        kind = "an attempt record" if first.startswith(HEADING) else "not the result"
        raise ValueError(f"{path}: first line {first!r} is {kind}, not {HEADING!r}")
    out: dict[str, dict] = {}
    head = "| specification | b | s | bbar |"
    try:
        start = next(i for i, ln in enumerate(lines) if ln.startswith(head))
    except StopIteration:
        raise ValueError(f"{path}: no specification table") from None
    for ln in lines[start + 2 :]:
        if not ln.startswith("|"):
            break
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) != len(FIELDS) + 1:
            raise ValueError(f"{path}: table row {ln!r} has {len(cells)} cells")
        out[cells[0]] = dict(zip(FIELDS, cells[1:], strict=True))
    if not {"H5", "H5b"} <= set(out):
        raise ValueError(f"{path}: the table lacks the H5 or H5b row")

    decision: dict[str, dict] = {}
    for i, ln in enumerate(lines):
        m = _DECISION.match(ln)
        if not m:
            continue
        hyp = m.group(1)
        ci = _CI.match(lines[i + 1])
        wording = _WORDING.match(lines[i + 2])
        mde = _MDE.match(lines[i + 3])
        if not (ci and wording and mde):
            raise ValueError(f"{path}: the {hyp} decision block is not as printed")
        decision[hyp] = {
            "holm_level": m.group(2),
            "rejected": m.group(3),
            "co_condition": m.group(4),
            "ci_005": (ci.group(1), ci.group(2)),
            "ci_0025": (ci.group(3), ci.group(4)),
            "wording": wording.group(1),
            "mde_r13": mde.group(1),
        }
    if set(decision) != {"H5", "H5b"}:
        raise ValueError(f"{path}: decision blocks found for {sorted(decision)}")
    out["decision"] = decision

    sec = {k: _one(p, lines, k).group(1) for k, p in _SECONDARY.items()}
    hc3 = _one(_HC3, lines, "HC3")
    sec.update(
        hc3_h5_b=hc3.group(1),
        hc3_h5_se=hc3.group(2),
        hc3_h5b_b=hc3.group(3),
        hc3_h5b_se=hc3.group(4),
    )
    out["secondary"] = sec

    m = {k: _one(p, lines, k) for k, p in _PROV.items()}
    out["provenance"] = {
        "commit": m["commit"].group(1),
        "tag_commit": m["commit"].group(2),
        "blob": m["blob"].group(1),
        "vector_sha256": m["vector_sha256"].group(1),
        "window": m["window"].group(1),
        "dates_read": m["window"].group(2),
        "n_days": m["window"].group(3),
        "n": m["n"].group(1),
        "dropped": m["n"].group(2).strip(),
    }
    return out
