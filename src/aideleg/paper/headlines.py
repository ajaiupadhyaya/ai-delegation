"""The headline registry and the red-team challenge log (Plan 4 Task 16).

`docs/redteam/headlines.csv` pre-declares every headline quantity before any prose exists: one row
per quantity, with the generated file it lives in and a locator that selects it. `resolve` reads a
row and returns the value exactly as the file prints it (a string; nothing is recomputed, rounded or
reformatted). `docs/redteam/challenges.csv` holds one row per (key, C1..C12) pair, and `render_log`
turns it into `docs/redteam/log.md`.

Locator grammar (`source_locator`; each kind must select exactly one value, else `ValueError`):

- `csv:<col>=<val>[,<col>=<val>...]:<value_col>` -- the rows of the CSV `source_file` whose
  columns equal every `<val>` (string comparison on the raw cell) must be exactly one; the value is
  that row's raw `<value_col>` cell. Neither `<col>` nor `<val>` may contain `,`, `=` or `:`.
- `json:<dotted.path>` -- walk the JSON object by keys; the target must be a scalar (not an object
  or list). A float is returned as Python's `repr`, which round-trips the stored value.
- `confirmatory_md:<dotted.path>[~<regex>]` -- walk the dict of `confirmatory_md.parse(source_file)`
  (the committed H5/H5b record; an attempt record is refused by the parser). A numeric segment
  indexes a tuple (`decision.H5.ci_005.0` is the interval's lower end). The target must be a
  string. With `~<regex>`, the regex (exactly one capture group) must match the string exactly once,
  and the value is the group; used to read the MDE out of the fixed P14 wording.
- `md-regex:<regex>` -- the regex (exactly one capture group, compiled with `re.MULTILINE`) must
  match the text of `source_file` exactly once; the value is the group.
- `config:`, `power_frozen:` or `pap:<dotted.path>` -- the built-in trees of
  `aideleg.paper.variables` (project constants, the frozen power values, the `pap-v1` tag), read by
  the same resolver the paper's variables use. Here `source_file` names the module or document
  that defines the constant; it is checked to exist but not read.

`source_file` is relative to the repository root (an absolute path is used as given).

AEI data are conversations matched to O*NET tasks.
"""

import csv
import json
import re
from pathlib import Path

import polars as pl

from aideleg.config import ROOT
from aideleg.paper import confirmatory_md
from aideleg.robustness.upstream import WORDING

HEADLINE_COLUMNS = ["key", "quantity", "source_file", "source_locator", "pap_section", "status"]
CHALLENGE_COLUMNS = ["key", "challenge", "check", "evidence", "outcome", "resolution", "commit"]
OUTCOMES = ("holds", "fails", "n/a")
# plus "fix logged as D-<n>"
RESOLUTIONS = ("none needed", "wording fixed", "label fixed", "STOP: confirmatory issue")

CHALLENGES = {
    "C1": "Reproduce. A clean rebuild (Task 33's fresh clone, or `make` in a clean worktree) gives "
    "the same printed value.",
    "C2": "Provenance. The value traces to one generated file, and its spec, sample and inference "
    "match the PAP section cited (quote the §).",
    "C3": "Timing. Every input that is claimed to be pre-formation is pre-formation. Look-ahead "
    "inputs are labelled.",
    "C4": "Protocol. For P-H5 and P-RQ1: the attempt marker, the single-run commit, no later edit "
    "to its files (`test_confirmatory_files_untouched`).",
    "C5": "Specification search. The value is the pre-registered primary or carries its "
    'robustness/exploratory label. No "best of" selection.',
    "C6": "Units. pp vs decimal, per SD, ×252, percent 0–100, years vs days.",
    "C7": "Sample accounting. n, dropped rows/industries and dropped shares are reported and "
    "reconcile with the source table.",
    "C8": "Influence. Softw/top-leverage units; the robustness rows that move the value most are "
    "named. This is reported, never changed.",
    "C9": "Testing family. The family, the Holm level and the α split are stated correctly. "
    "Variants are not counted.",
    "C10": "Wording. AEI usage wording; P14 wording for non-rejections; no causal claim; equal "
    "prominence for nulls.",
    "C11": "Uncertainty. CI and p are present. The MDE sits beside each market null.",
    "C12": "Alternative explanations. Classifier and platform drift (H2), suppression and the R7 "
    "bounds (H1/H3), task mix (H4), tech beta (R7 row) and collinearity (H5b).",
}


HEADLINES = ROOT / "docs/redteam/headlines.csv"
# Task 31: the parts of the paper whose variables are headline numbers
HEADLINE_SOURCES = (
    "docs/paper/sections/00-abstract.qmd",
    "docs/paper/brief_body.qmd",
    "docs/paper/sections/01-introduction.qmd",
    "docs/paper/sections/10-conclusion.qmd",
)
_VAR = re.compile(r"\{\{<\s*var\s+([^\s>]+)\s*>\}\}")
_BUILTIN_KINDS = ("config", "power_frozen", "pap")
# the file that defines each built-in constant (`source_file` of a built-in headline row)
_BUILTIN_FILES = {
    "config.releases": "src/aideleg/config.py",
    "config.seal_date": "src/aideleg/config.py",
    "config.seed": "src/aideleg/config.py",
    "config.window": "src/aideleg/confirm_h5.py",
    "config.n_industries": "src/aideleg/h6/edgar.py",
    "config.plausibility_pp": "src/aideleg/power.py",
    "power_frozen": "src/aideleg/confirm_h5.py",
    "pap": "docs/pap/pre-analysis-plan.md",
}


def _path(source_file: str) -> Path:
    p = Path(source_file)
    return p if p.is_absolute() else ROOT / p


def _one_group(pattern: str, text: str, what: str) -> str:
    rx = re.compile(pattern, re.MULTILINE)
    if rx.groups != 1:
        raise ValueError(f"{what}: {pattern!r} has {rx.groups} groups, expected 1")
    found = [m.group(1) for m in rx.finditer(text)]
    if len(found) != 1:
        raise ValueError(f"{what}: {pattern!r} matched {len(found)} times, expected 1")
    return found[0]


def _csv(path: Path, spec: str) -> str:
    conds, sep, col = spec.rpartition(":")
    if not sep or not conds or not col:
        raise ValueError(f"csv locator {spec!r}: expected <col>=<val>[,...]:<value_col>")
    pairs = [c.split("=", 1) for c in conds.split(",")]
    if any(len(p) != 2 for p in pairs):
        raise ValueError(f"csv locator {spec!r}: a condition is not <col>=<val>")
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    header = set(rows[0]) if rows else set()
    unknown = [c for c, _ in pairs if c not in header] + ([col] if col not in header else [])
    if unknown:
        raise ValueError(f"{path.name}: no column(s) {unknown}")
    hits = [r for r in rows if all(r[c] == v for c, v in pairs)]
    if len(hits) != 1:
        raise ValueError(f"{path.name}: {conds!r} selects {len(hits)} rows, expected 1")
    return hits[0][col]


def _walk(obj, dotted: str, what: str):
    for seg in dotted.split("."):
        if isinstance(obj, dict) and seg in obj:
            obj = obj[seg]
        elif isinstance(obj, (tuple, list)) and seg.isdigit() and int(seg) < len(obj):
            obj = obj[int(seg)]
        else:
            raise ValueError(f"{what}: no {seg!r} in {dotted!r}")
    return obj


def _json(path: Path, dotted: str) -> str:
    v = _walk(json.loads(path.read_text(encoding="utf-8")), dotted, path.name)
    if isinstance(v, (dict, list)) or v is None:
        raise ValueError(f"{path.name}: {dotted!r} is not a scalar")
    return repr(v) if isinstance(v, float) else str(v)


def _confirmatory(path: Path, spec: str) -> str:
    dotted, tilde, pattern = spec.partition("~")
    v = _walk(confirmatory_md.parse(path), dotted, path.name)
    if not isinstance(v, str):
        raise ValueError(f"{path.name}: {dotted!r} is a {type(v).__name__}, not one value")
    return _one_group(pattern, v, f"{path.name} {dotted}") if tilde else v


def resolve(row: dict) -> str:
    """The value that `row["source_locator"]` selects in `row["source_file"]`, as printed."""
    path = _path(row["source_file"])
    kind, sep, spec = row["source_locator"].partition(":")
    if not sep:
        raise ValueError(f"locator {row['source_locator']!r} has no kind")
    if kind == "csv":
        return _csv(path, spec)
    if kind == "json":
        return _json(path, spec)
    if kind == "confirmatory_md":
        return _confirmatory(path, spec)
    if kind == "md-regex":
        return _one_group(spec, path.read_text(encoding="utf-8"), path.name)
    if kind in _BUILTIN_KINDS:
        from aideleg.paper import variables  # variables imports this module

        return str(variables._builtin(kind, spec))
    raise ValueError(f"unknown locator kind {kind!r}")


def _cell(v) -> str:
    return "" if v is None else str(v).replace("|", "\\|").replace("\n", " ")


def render_log(challenges: pl.DataFrame) -> str:
    """`docs/redteam/log.md`: the fixed challenge list, then one table per headline key (in the
    order the keys first appear), each row a challenge with its check, evidence and outcome."""
    missing = [c for c in CHALLENGE_COLUMNS if c not in challenges.columns]
    if missing:
        raise ValueError(f"challenges lack column(s) {missing}")
    parts = [
        "Generated by `aideleg.paper.headlines.render_log` from `docs/redteam/challenges.csv`. "
        "Do not edit by hand.",
        "",
        "# Red-team log: every headline number",
        "",
        WORDING,
        "",
        "## Challenges",
        "",
    ]
    parts += [f"- **{cid}** {text}" for cid, text in CHALLENGES.items()]
    order = list(dict.fromkeys(challenges["key"].to_list()))
    rank = {c: i for i, c in enumerate(CHALLENGES)}
    for key in order:
        sub = challenges.filter(pl.col("key") == key).to_dicts()
        sub.sort(key=lambda r: rank.get(r["challenge"], len(rank)))
        parts += [
            "",
            f"## `{key}`",
            "",
            "| challenge | check | evidence | outcome | resolution | commit |",
            "|---|---|---|---|---|---|",
        ]
        for r in sub:
            label = r["challenge"]
            if label in CHALLENGES:
                label = f"{label} {CHALLENGES[label].split('.', 1)[0]}"
            cells = [label] + [
                r[c] for c in ("check", "evidence", "outcome", "resolution", "commit")
            ]
            parts.append("| " + " | ".join(_cell(c) for c in cells) + " |")
    return "\n".join(parts) + "\n"


def scan_headlines(
    sources: tuple[str, ...] = HEADLINE_SOURCES, registry: Path = HEADLINES
) -> list[str]:
    """Every `{{< var key >}}` used in `sources` (in order of first use) that is not already,
    case-insensitively, a key of `registry`."""
    with open(registry, newline="", encoding="utf-8") as f:
        known = {r["key"].lower() for r in csv.DictReader(f)}
    used: dict[str, None] = {}
    for src in sources:
        for key in _VAR.findall(_path(src).read_text(encoding="utf-8")):
            used.setdefault(key, None)
    return [k for k in used if k.lower() not in known]


def locate_variable(map_row: dict) -> tuple[str, str]:
    """`(source_file, source_locator)` for a row of `docs/paper/variables_map.csv`, in this
    module's locator grammar, so that `resolve` reads the raw value `variables.resolve` reads."""
    source, loc = map_row["source"], map_row["locator"]
    if source == "confirmatory_md":
        return confirmatory_md.PATH.relative_to(ROOT).as_posix(), f"confirmatory_md:{loc}"
    if source in _BUILTIN_KINDS:
        head = source if source != "config" else f"config.{loc.split('.', 1)[0]}"
        if head not in _BUILTIN_FILES:
            raise ValueError(f"{source}:{loc}: no defining file known")
        return _BUILTIN_FILES[head], f"{source}:{loc}"
    suffix = Path(source).suffix
    if suffix == ".csv":
        from aideleg.paper import variables

        col, pairs = variables._csv_spec(loc)
        if not pairs:
            raise ValueError(f"{source}: a headline csv locator needs a filter")
        return source, "csv:" + ",".join(f"{c}={v}" for c, v in pairs) + f":{col}"
    if suffix == ".json":
        return source, f"json:{loc}"
    if suffix == ".md" and loc.startswith("regex="):
        return source, "md-regex:" + loc[len("regex=") :]
    raise ValueError(f"{source}: {loc!r} has no headline locator")
