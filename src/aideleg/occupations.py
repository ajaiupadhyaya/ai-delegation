"""Occupation table: AEI conversations matched to O*NET tasks, allocated to SOC occupations.

AEI data are conversations matched to O*NET tasks. An occupation row here describes the
conversations matched to that occupation's tasks; it says nothing about workers, jobs or the
labour market.

One table per release, keyed by `(release, period_start, source, soc6)`: r6 has two monthly
periods, and r3-r6 have both `claude_ai` and `1p_api` sources. Only the GLOBAL rows of the
panel are used.

Bases
- `"tasks"`: task rows (`taxonomy == "onet_task"`) are allocated to occupations. A task's
  occupations are the union, over every candidate Task ID of its statement
  (`TaskIndex.occupations_for_text(node_name)`) and its panel `node_id`, of the O*NET-SOC 2019
  codes, truncated to `soc6 = NN-NNNN`. Never one representative ID alone.
  `"equal"`: a task shared by k soc6 occupations gives `pct / k` to each (usage conserved).
  `"full"`: each gets the full `pct` (sensitivity only; usage is not conserved).
  Nodes `unmatched:*` (AEI sentinels `none` / `not_classified`, and task texts with no Task
  ID) and matched tasks with no indexed occupation are not allocated; `unallocated_mass`
  reports their pct per release, period and source.
- `"published"`: r6 publishes `soc_detailed` rows (O*NET-SOC `NN-NNNN.NN`). They are
  aggregated to soc6 with the same weighting as tasks (weights = published pct). This is the
  r6 default; the task-allocated r6 table is a check on it.

Columns
- `usage_share`: the sum of allocated pct, in percent of all conversations in that release,
  period and source (as published; not renormalised over matched or published mass).
- Pattern shares `automation_pct, augmentation_pct, directive_pct, feedback_loop_pct,
  task_iteration_pct, validation_pct, learning_pct`: usage-weighted means over the
  occupation's tasks with a non-null value of that metric, weights = the tasks' allocated
  pct. As in the panel, they are renormalised over classified conversations (excluding
  filtered / none / not_classified) and automation = directive + feedback_loop,
  augmentation = task_iteration + validation + learning.
- `suppressed_pct`: the usage-weighted mean of the task's suppressed share, a share of all
  of the task's conversations: r2 `filtered_pct`; r3-r5 `not_classified_pct + none_pct`;
  r6 `none_pct`; r1 has no task-level collaboration, so null. A task's value is null unless
  every component is published.
- `automation_share_all_lb = automation_pct * (100 - suppressed_pct) / 100` (suppressed
  conversations counted as non-automation) and
  `automation_share_all_ub = automation_share_all_lb + suppressed_pct` (counted as
  automation). Both are computed per task (null unless both inputs are published) and then
  aggregated with the same usage weights, so the occupation values are not the product of the
  occupation-level means. Which of `automation_pct`, lb and ub is primary is left to the
  pre-analysis plan.
- `n_tasks`: distinct task nodes allocated to the occupation (null for the published basis).
- `basis`: `"tasks"` or `"published"`.

`soc_rollup` maps a detailed SOC code to the OEWS aggregate that contains it when OEWS
publishes only the aggregate (a code ending in `0`, such as `15-1250`).
"""

from typing import Literal

import polars as pl

from aideleg.aei.tasks import TaskIndex

KEY = ["release", "period_start", "source"]
PATTERNS = ["automation_pct", "augmentation_pct", "directive_pct", "feedback_loop_pct",
            "task_iteration_pct", "validation_pct", "learning_pct"]
SUPPRESSION: dict[str, tuple[str, ...] | None] = {
    "r1": None,
    "r2": ("filtered_pct",),
    "r3": ("not_classified_pct", "none_pct"),
    "r4": ("not_classified_pct", "none_pct"),
    "r5": ("not_classified_pct", "none_pct"),
    "r6": ("none_pct",),
}
BOUNDS = ["suppressed_pct", "automation_share_all_lb", "automation_share_all_ub"]
MEASURES = PATTERNS + BOUNDS
COLUMNS = KEY + ["basis", "soc6", "usage_share", *MEASURES, "n_tasks"]
_SUPP_METRICS = ("filtered_pct", "none_pct", "not_classified_pct")


def _wide(panel: pl.DataFrame, release: str, taxonomy: str) -> pl.DataFrame:
    """One row per GLOBAL node: KEY, node_id, node_name, pct, patterns and bounds."""
    metrics = ["pct", *PATTERNS, *_SUPP_METRICS]
    long = panel.filter(
        (pl.col("release") == release) & (pl.col("taxonomy") == taxonomy)
        & (pl.col("geo_level") == "global") & pl.col("metric").is_in(metrics)
    )
    names = long.group_by(*KEY, "node_id").agg(pl.col("node_name").first())
    if long.is_empty():
        wide = long.select(*KEY, "node_id")
    else:
        wide = long.pivot(on="metric", index=[*KEY, "node_id"], values="value",
                          aggregate_function=None)
    wide = wide.with_columns(
        [pl.lit(None, pl.Float64).alias(m) for m in metrics if m not in wide.columns]
    ).join(names, on=[*KEY, "node_id"], how="left")

    comps = SUPPRESSION.get(release)
    if comps is None:
        supp = pl.lit(None, pl.Float64)
    else:
        published = pl.all_horizontal([pl.col(c).is_not_null() for c in comps])
        supp = pl.when(published).then(pl.sum_horizontal(comps))
    lb = pl.col("automation_pct") * (100 - pl.col("suppressed_pct")) / 100
    return (wide.with_columns(suppressed_pct=supp)
            .with_columns(automation_share_all_lb=lb)
            .with_columns(automation_share_all_ub=pl.col("automation_share_all_lb")
                          + pl.col("suppressed_pct")))


def _task_occupations(nodes: pl.DataFrame, index: TaskIndex) -> pl.DataFrame:
    """node_id, node_name -> sorted list of soc6 codes (union over candidate Task IDs)."""
    occs = []
    for node_id, name in nodes.select("node_id", "node_name").iter_rows():
        codes = set(index.occupations_for_text(name)) if name is not None else set()
        if node_id.isdigit():
            codes |= set(index.occupations_for(int(node_id)))
        occs.append(sorted({c[:7] for c in codes}))
    return nodes.select("node_id", "node_name").with_columns(
        soc6=pl.Series(occs, dtype=pl.List(pl.String)))


_MATCHED = ~pl.col("node_id").str.starts_with("unmatched:") & pl.col("pct").is_not_null()


def _aggregate(contrib: pl.DataFrame, basis: str, count_tasks: bool) -> pl.DataFrame:
    """contrib: KEY, soc6, node_id, w, measures -> one row per KEY, soc6."""
    aggs = [pl.col("w").sum().alias("usage_share")]
    for m in MEASURES:
        has = pl.col(m).is_not_null()
        den = pl.col("w").filter(has).sum()
        aggs.append(pl.when(den > 0).then((pl.col("w") * pl.col(m)).filter(has).sum() / den)
                    .alias(m))
    aggs.append(pl.col("node_id").n_unique().cast(pl.Int64).alias("n_tasks") if count_tasks
                else pl.lit(None, pl.Int64).alias("n_tasks"))
    out = contrib.group_by(*KEY, "soc6").agg(aggs).with_columns(basis=pl.lit(basis))
    return out.select(COLUMNS).sort(KEY + ["soc6"])


def _from_tasks(panel: pl.DataFrame, release: str, index: TaskIndex,
                allocation: str) -> pl.DataFrame:
    wide = _wide(panel, release, "onet_task").filter(_MATCHED)
    occ = _task_occupations(wide.select("node_id", "node_name").unique(), index)
    rows = wide.join(occ, on=["node_id", "node_name"], how="left",
                       nulls_equal=True).filter(
        pl.col("soc6").list.len() > 0)
    k = pl.col("soc6").list.len()
    w = pl.col("pct") / k if allocation == "equal" else pl.col("pct")
    contrib = rows.with_columns(w=w).explode("soc6")
    return _aggregate(contrib, "tasks", count_tasks=True)


def _from_published(panel: pl.DataFrame, release: str) -> pl.DataFrame:
    wide = _wide(panel, release, "soc_detailed").filter(pl.col("pct").is_not_null())
    contrib = wide.with_columns(soc6=pl.col("node_id").str.slice(0, 7), w=pl.col("pct"))
    return _aggregate(contrib, "published", count_tasks=False)


def occupation_table(
    panel: pl.DataFrame,
    release: str,
    index: TaskIndex,
    allocation: Literal["equal", "full"] = "equal",
    basis: Literal["auto", "tasks", "published"] = "auto",
) -> pl.DataFrame:
    """Occupation table for one release; columns `COLUMNS` (see the module docstring).

    `basis="auto"` uses the published soc_detailed rows for r6 and task allocation otherwise.
    `allocation` applies to the task basis only.
    """
    if allocation not in ("equal", "full"):
        raise ValueError(f"allocation must be 'equal' or 'full', not {allocation!r}")
    if basis == "auto":
        basis = "published" if release == "r6" else "tasks"
    if basis == "published":
        return _from_published(panel, release)
    if basis == "tasks":
        return _from_tasks(panel, release, index, allocation)
    raise ValueError(f"basis must be 'auto', 'tasks' or 'published', not {basis!r}")


def unallocated_mass(panel: pl.DataFrame, release: str, index: TaskIndex) -> pl.DataFrame:
    """Task pct left out of the allocation, per KEY and reason.

    reason `unmatched`: `unmatched:*` nodes (AEI sentinels and texts with no Task ID);
    reason `no_occupation`: matched Task IDs with no occupation in the index.
    """
    wide = _wide(panel, release, "onet_task").filter(pl.col("pct").is_not_null())
    un = wide.filter(pl.col("node_id").str.starts_with("unmatched:")).with_columns(
        reason=pl.lit("unmatched"))
    matched = wide.filter(~pl.col("node_id").str.starts_with("unmatched:"))
    occ = _task_occupations(matched.select("node_id", "node_name").unique(), index)
    none = (matched.join(occ, on=["node_id", "node_name"], how="left",
                       nulls_equal=True)
            .filter(pl.col("soc6").list.len() == 0)
            .with_columns(reason=pl.lit("no_occupation")).drop("soc6"))
    both = pl.concat([un, none], how="diagonal")
    return (both.group_by(*KEY, "reason")
            .agg(n_nodes=pl.len().cast(pl.Int64), pct=pl.col("pct").sum())
            .sort(KEY + ["reason"]))


def soc_rollup(soc6: str, oews_codes: set[str]) -> str:
    """The OEWS code that holds `soc6`: itself if OEWS publishes it, else its OEWS aggregate.

    An aggregate is a code ending in `0` (a SOC broad group, e.g. `15-1250`) present in
    `oews_codes`; detailed SOC 2018 codes never end in `0`. A code with neither is returned
    unchanged, for the caller to report as unmatched.
    """
    if soc6 in oews_codes:
        return soc6
    broad = soc6[:-1] + "0"
    return broad if broad in oews_codes else soc6
