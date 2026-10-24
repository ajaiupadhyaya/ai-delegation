"""The paper's variables: `docs/paper/variables_map.csv` -> `docs/paper/_variables.yml` (Plan 4
Task 18).

Every number the paper prints outside a generated include is a `{{< var key >}}` shortcode, and
every key is one row of `variables_map.csv` (`key, source, locator, fmt`). `build` resolves each
row to exactly one value, formats it and nests the keys on `.`; `write` stores the result as JSON
with sorted keys (JSON is valid YAML 1.2, which Quarto reads). Nothing is typed by hand.

Sources and locators:

- a repo-relative `.csv`: `column=<col>;filter=<col>:<val>[,<col>:<val>...]` (the filter may be
  omitted when the file has one row). The rows whose raw cells equal every `<val>` must be exactly
  one; matching is `headlines`' CSV resolver, so a `<val>` may not hold `,`, `=` or `:`.
- a repo-relative `.json`: a dotted path (`headlines`' JSON resolver).
- a repo-relative `.md`: `regex=<regex>` with one capture group matching exactly once
  (`re.MULTILINE`).
- `confirmatory_md`: a dotted path into `confirmatory_md.parse()` (the committed H5/H5b record),
  optionally `~<regex>` to read a number out of a printed string (`headlines`' resolver).
- `config`: a dotted path into `config_values()` (release dates, the Design B window, the seal
  date, SEED, the FF49 industry count, the D11 plausibility threshold, the results date).
- `power_frozen`: a dotted path into `power_values()`, computed from `confirm_h5.FROZEN`
  (MDE = (c_0.025 + t_21,0.80) * s, in pp).
- `pap`: a dotted path into `pap_values()` (the `pap-v1` tag, its commit and date). The PAP is
  frozen, so commit and date are pinned here (`PAP_COMMIT`, `PAP_DATE`) and checked against git
  when the tag is available.

Without git history (an archive with no `.git`, or a shallow clone), `meta.date` is read from the
committed `_variables.yml`, so the build is the same as from a full clone.

Formats (`fmt`; Global Constraints): `pp` and `coef` 2 decimals; `rho` 3 decimals; `p` 3
decimals with p < 0.001 shown as "< 0.001"; `pct` 2 decimals (percent 0-100, no sign); `int`;
`text` verbatim; `date` ISO. A value read from a printed markdown file (`confirmatory_md` or a
`.md` regex) keeps the precision it was printed with: the format only checks that it is a
number of the right kind. Negative numbers keep the ASCII hyphen the tables print.
Two prose forms: `pp2` is 2 decimals even for a printed value (so prose never mixes precisions);
`verdict` turns a decision into words (`True`/`False` -> "rejected"/"not rejected";
the RQ1 status `supported`/`not_rejected` -> "supported"/"not supported"; any other value is
refused).

Default (Task 18): a red-team headline key of `docs/redteam/headlines.csv` is the variable of the
same name lower-cased (`rq1.H1.beta_e` -> `rq1.h1.beta_e`), with the same value as formatted.

AEI data are conversations matched to O*NET tasks.
"""

import csv
import json
import math
import re
import subprocess
from datetime import date
from functools import cache
from pathlib import Path

from aideleg.config import PAP_TAG, RELEASES, ROOT, SEAL_DATE, SEED
from aideleg.paper import confirmatory_md, headlines

MAP = ROOT / "docs/paper/variables_map.csv"
OUT = ROOT / "docs/paper/_variables.yml"
COLUMNS = ["key", "source", "locator", "fmt"]
FMTS = ("pp", "coef", "rho", "p", "int", "pct", "text", "date", "pp2", "verdict")
VERDICTS = {
    "True": "rejected",
    "False": "not rejected",
    "supported": "supported",
    "not_rejected": "not supported",
}
# pap-v1 (frozen): checked against git when the tag is present
PAP_COMMIT = "6a16b1ad052977650b90c8062ceeeab9ac6572e1"
PAP_DATE = "2026-10-21"
BUILTINS = ("confirmatory_md", "config", "power_frozen", "pap")
NUMERIC = ("pp", "coef", "rho", "p", "int", "pct")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")
# the paths whose last commit dates the generated numbers (meta.date)
DATED = ("docs/results", "docs/paper/figures", "docs/pap/power.md", "docs/audit/tables")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _float(value, kind: str) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{value!r} is not a number ({kind})") from None
    if not math.isfinite(x):
        raise ValueError(f"{value!r} is not finite ({kind})")
    return x


def fmt(value, kind: str, *, printed: bool = False) -> str:
    """`value` formatted by `kind` (see the module docstring). With `printed`, a string read from
    a printed markdown file is returned as printed after checking it is a number."""
    if kind not in FMTS:
        raise ValueError(f"unknown format {kind!r}; expected one of {FMTS}")
    if kind == "text":
        return str(value)
    if kind == "verdict":
        if str(value) not in VERDICTS:
            raise ValueError(f"{value!r} is not a known decision {sorted(VERDICTS)}")
        return VERDICTS[str(value)]
    if kind == "pp2":
        return f"{_float(value, kind):.2f}"
    if kind == "date":
        s = value.isoformat() if isinstance(value, date) else str(value)
        if not _DATE.match(s):
            raise ValueError(f"{value!r} is not an ISO date")
        date.fromisoformat(s)
        return s
    if printed and isinstance(value, str):
        s = value.strip()
        if not _NUMBER.match(s):
            raise ValueError(f"printed value {value!r} is not a number ({kind})")
        if kind == "int" and "." in s:
            raise ValueError(f"printed value {value!r} is not an integer")
        return s
    x = _float(value, kind)
    if kind in ("pp", "coef", "pct"):
        return f"{x:.2f}"
    if kind == "rho":
        return f"{x:.3f}"
    if kind == "p":
        return "< 0.001" if x < 0.001 else f"{x:.3f}"
    if x != int(x):
        raise ValueError(f"{value!r} is not an integer")
    return str(int(x))


def _git(repo: Path, *args: str) -> str | None:
    """git's output in `repo`, or None when git, the repository or the object is unavailable."""
    try:
        r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    except OSError:
        return None
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _has_history(repo: Path) -> bool:
    top = _git(repo, "rev-parse", "--show-toplevel")
    if top is None or Path(top).resolve() != Path(repo).resolve():
        return False
    return _git(repo, "rev-parse", "--is-shallow-repository") == "false"


def results_date(repo: Path = ROOT) -> str:
    """The last commit date of the generated inputs (`DATED`): fixed until a result changes.
    Without full git history, the `meta.date` of the committed `_variables.yml`."""
    if _has_history(repo):
        d = _git(repo, "log", "-1", "--format=%cs", "--", *DATED)
        if d:
            return d
    committed = Path(repo) / OUT.relative_to(ROOT)
    try:
        return json.loads(committed.read_text(encoding="utf-8"))["meta"]["date"]
    except (OSError, ValueError, KeyError) as e:
        raise ValueError(f"no git history and no committed meta.date in {committed}: {e}") from None


@cache
def config_values() -> dict:
    """Project constants for `design.*` and `meta.date`."""
    from aideleg import confirm_h5, power
    from aideleg.h6.edgar import FF49_INDUSTRIES

    return {
        "releases": dict(RELEASES),
        "window": {"start": confirm_h5.WINDOW[0], "end": confirm_h5.WINDOW[1]},
        "seal_date": SEAL_DATE,
        "seed": SEED,
        "n_industries": len(FF49_INDUSTRIES),
        "plausibility_pp": power.PLAUSIBILITY_PP,
        # the last commit date of the generated inputs: fixed until a result changes
        "results_date": results_date(ROOT),
    }


@cache
def power_values() -> dict:
    """The frozen null scales of `confirm_h5.FROZEN` in pp, and the P14 MDEs computed from
    them: (c_0.025 + t_21,0.80) * s for every specification."""
    from scipy import stats

    from aideleg.confirm_h5 import FROZEN, T_DF, VARIANTS

    t80 = float(stats.t.ppf(0.80, T_DF))
    return {
        "mde": {v: (FROZEN[f"crit_{v}_0.025"] + t80) * FROZEN[f"s_{v}"] * 100 for v in VARIANTS},
        "s": {v: FROZEN[f"s_{v}"] * 100 for v in VARIANTS},
        "bbar": {v: FROZEN[f"bbar_{v}"] * 100 for v in VARIANTS},
        "crit_0025": FROZEN["t21_0.025"],
        "crit_005": FROZEN["t21_0.05"],
        "t_df": T_DF,
        "power_pct": 80,
        "holm_first": 0.025,
    }


def pap_values(repo: Path = ROOT) -> dict:
    """The pinned `pap-v1` commit and date; where git has the tag, they must agree with it."""
    if _has_history(repo):
        got = {
            "commit": _git(repo, "rev-list", "-n", "1", PAP_TAG),
            "date": _git(repo, "log", "-1", "--format=%cs", PAP_TAG),
        }
        want = {"commit": PAP_COMMIT, "date": PAP_DATE}
        for k, v in got.items():
            if v is not None and v != want[k]:
                raise ValueError(f"{PAP_TAG} {k} is {v} in git, pinned {want[k]}")
    return {"tag": PAP_TAG, "commit": PAP_COMMIT, "date": PAP_DATE}


def _builtin(source: str, locator: str):
    if source == "confirmatory_md":
        return headlines._confirmatory(confirmatory_md.PATH, locator)
    tree = {"config": config_values, "power_frozen": power_values, "pap": pap_values}[source]()
    v = headlines._walk(tree, locator, source)
    if isinstance(v, (dict, list, tuple)):
        raise ValueError(f"{source}: {locator!r} is not one value")
    return v


def _csv_spec(locator: str) -> tuple[str, list[tuple[str, str]]]:
    parts = dict(p.split("=", 1) for p in locator.split(";") if "=" in p)
    if "column" not in parts or set(parts) - {"column", "filter"} or locator.count(";") > 1:
        raise ValueError(f"csv locator {locator!r}: expected column=<col>[;filter=<col>:<val>,...]")
    pairs = []
    for cond in parts.get("filter", "").split(",") if parts.get("filter") else []:
        col, sep, val = cond.partition(":")
        if not sep or not col or "=" in val or ":" in val:
            raise ValueError(f"csv locator {locator!r}: bad condition {cond!r}")
        pairs.append((col, val))
    return parts["column"], pairs


def resolve(row: dict) -> tuple[object, bool]:
    """The raw value a map row selects, and whether it was read from printed markdown."""
    source, locator = row["source"], row["locator"]
    if source in BUILTINS:
        return _builtin(source, locator), source == "confirmatory_md"
    path = headlines._path(source)
    if path.suffix == ".csv":
        col, pairs = _csv_spec(locator)
        if pairs:
            spec = ",".join(f"{c}={v}" for c, v in pairs) + f":{col}"
            return headlines._csv(path, spec), False
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1 or col not in rows[0]:
            raise ValueError(f"{path.name}: no filter needs exactly one row with {col!r}")
        return rows[0][col], False
    if path.suffix == ".json":
        return headlines._json(path, locator), False
    if path.suffix == ".md":
        if not locator.startswith("regex="):
            raise ValueError(f"markdown locator {locator!r}: expected regex=<regex>")
        text = path.read_text(encoding="utf-8")
        return headlines._one_group(locator[len("regex=") :], text, path.name), True
    raise ValueError(f"unknown source {source!r}")


def _nest(flat: dict[str, str]) -> dict:
    out: dict = {}
    for key in sorted(flat):
        node = out
        *head, last = key.split(".")
        for i, seg in enumerate(head):
            node = node.setdefault(seg, {})
            if not isinstance(node, dict):
                raise ValueError(f"{key}: {'.'.join(head[: i + 1])} is already a value")
        if last in node:
            raise ValueError(f"{key}: already holds nested keys")
        node[last] = flat[key]
    return out


def build(map_path: Path = MAP) -> dict:
    """Resolve, format and nest every row of `map_path`. A row that does not resolve to exactly
    one value raises `ValueError` naming its key."""
    with open(map_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"{map_path}: columns {reader.fieldnames}, expected {COLUMNS}")
        rows = list(reader)
    flat: dict[str, str] = {}
    for row in rows:
        key = row["key"]
        if not KEY_RE.match(key):
            raise ValueError(f"{key!r}: not a lower-case dotted key")
        if key in flat:
            raise ValueError(f"{key}: mapped twice")
        try:
            value, printed = resolve(row)
            flat[key] = fmt(value, row["fmt"], printed=printed)
        except ValueError as e:
            raise ValueError(f"{key}: {e}") from None
    return _nest(flat)


def write(vars: dict, out: Path = OUT) -> Path:
    out.write_text(json.dumps(vars, indent=2, sort_keys=True, ensure_ascii=False) + "\n", "utf-8")
    return out
