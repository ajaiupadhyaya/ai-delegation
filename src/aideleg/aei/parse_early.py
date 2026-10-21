"""Parsers for AEI releases r1 (2025-02-10) and r2 (2025-03-27), whose files are keyed by task name.

AEI data are conversations matched to O*NET tasks; nothing here says anything about jobs.
Paths passed in are the release folders (e.g. data/raw/aei/r1).

Period windows: the windows below are those given in the release reports (r1 paper and r2
report). The Hugging Face README files of release_2025_02_10 and release_2025_03_27 state
no data window, so the defaults stand.
"""

from datetime import date
from pathlib import Path

import polars as pl

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex, match_tasks, normalise_task_text

_PERIOD = {
    "r1": (date(2024, 12, 1), date(2025, 1, 1)),
    "r2": (date(2025, 2, 24), date(2025, 3, 4)),
}
_DEFINITION = {"r1": "collab_v1", "r2": "collab_v2"}
_PATTERNS = ["feedback_loop", "directive", "task_iteration", "validation", "learning"]
_AUTOMATION = ["directive", "feedback_loop"]
# interaction types outside the classified denominator
_UNCLASSIFIED = {"none", "filtered", "not_classified"}


_Row = tuple[str, str, str, float | None]


def _frame(release: str, taxonomy: str, rows: list[_Row]) -> pl.DataFrame:
    """rows: (node_id, node_name, metric, value) -> PANEL_COLUMNS frame (level 0)."""
    start, end = _PERIOD[release]
    return pl.DataFrame(
        {
            "release": release,
            "period_start": start,
            "period_end": end,
            "source": "claude_ai",
            "geo_level": "global",
            "geo_id": "GLOBAL",
            "taxonomy": taxonomy,
            "level": 0,
            "node_id": [r[0] for r in rows],
            "node_name": [r[1] for r in rows],
            "metric": [r[2] for r in rows],
            "value": [r[3] for r in rows],
            "definition": _DEFINITION[release],
        },
        schema={
            "release": pl.String, "period_start": pl.Date, "period_end": pl.Date,
            "source": pl.String, "geo_level": pl.String, "geo_id": pl.String,
            "taxonomy": pl.String, "level": pl.Int64, "node_id": pl.String,
            "node_name": pl.String, "metric": pl.String, "value": pl.Float64,
            "definition": pl.String,
        },
    ).select(PANEL_COLUMNS)


def _node_ids(names: pl.Series, index: TaskIndex) -> list[str]:
    """Matched O*NET Task ID as a string, else `unmatched:<normalised text>`.

    The r1 sentinel row `none` is not an O*NET task; it stays as `unmatched:none` so the
    published shares still sum to 100.
    """
    m = match_tasks(names, index)
    return [
        str(t) if t is not None else f"unmatched:{normalise_task_text(n)}"
        for n, t in zip(m["task_name"], m["task_id"], strict=True)
    ]


def _task_pct(release: str, path: Path, index: TaskIndex) -> list[_Row]:
    # Verified on the real files: `pct` is already in percent (it sums to 100), whatever the
    # release README implies, so it is kept as published, not multiplied by 100.
    df = pl.read_csv(path, schema_overrides={"task_name": pl.String, "pct": pl.Float64})
    ids = _node_ids(df["task_name"], index)
    return [(i, n, "pct", p)
            for i, n, p in zip(ids, df["task_name"], df["pct"], strict=True)]


def parse_r1(raw: Path, index: TaskIndex) -> pl.DataFrame:
    """r1: task shares and the overall collaboration split.

    Overall `<type>_pct` are shares of classified conversations (the five patterns);
    `none_pct` is the published share of all conversations, outside that denominator.
    """
    rows = _task_pct("r1", raw / "onet_task_mappings.csv", index)
    tasks = _frame("r1", "onet_task", rows)

    c = pl.read_csv(raw / "automation_vs_augmentation.csv")
    types = [t.strip().lower().replace(" ", "_") for t in c["interaction_type"]]
    vals = dict(zip(types, c["pct"], strict=True))
    classified = {k: v for k, v in vals.items() if k not in _UNCLASSIFIED}
    total = sum(classified.values())
    out: list[_Row] = []
    for k in sorted(vals):
        if k in _UNCLASSIFIED:
            out.append(("overall", "overall", f"{k}_pct", vals[k]))
        else:
            out.append(("overall", "overall", f"{k}_pct", vals[k] / total * 100))
    auto = sum(v for k, v in classified.items() if k in _AUTOMATION) / total * 100
    out.append(("overall", "overall", "automation_pct", auto))
    out.append(("overall", "overall", "augmentation_pct", 100 - auto))
    return pl.concat([tasks, _frame("r1", "overall", out)])


def parse_r2(raw: Path, index: TaskIndex) -> pl.DataFrame:
    """r2: task shares plus per-task collaboration patterns.

    `filtered_pct` is the share of the task's conversations that were filtered; each
    pattern is renormalised over the rest. A task with filtered == 1 has no classified
    conversations, so its pattern metrics are null (not 0).
    """
    tasks = _frame("r2", "onet_task", _task_pct("r2", raw / "task_pct_v2.csv", index))

    c = pl.read_csv(raw / "automation_vs_augmentation_by_task.csv")
    ids = _node_ids(c["task_name"], index)
    out: list[_Row] = []
    for i, row in zip(ids, c.iter_rows(named=True), strict=True):
        n = row["task_name"]
        f = row["filtered"]
        out.append((i, n, "filtered_pct", f * 100))
        if f < 1:
            sh = {p: row[p] / (1 - f) * 100 for p in _PATTERNS}
            auto = sum(sh[p] for p in _AUTOMATION)
            aug: float | None = sum(v for p, v in sh.items() if p not in _AUTOMATION)
        else:
            sh = {p: None for p in _PATTERNS}
            auto, aug = None, None
        for p in _PATTERNS:
            out.append((i, n, f"{p}_pct", sh[p]))
        out.append((i, n, "automation_pct", auto))
        out.append((i, n, "augmentation_pct", aug))
    return pl.concat([tasks, _frame("r2", "onet_task", out)])
