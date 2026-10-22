"""H1/H3 unit of observation: (task statement, occupation, task family) rows (PAP §4.1).

AEI data are conversations matched to O*NET tasks. A row describes the conversations matched
to one task, allocated to one occupation and one task family. It says nothing about workers,
jobs or the labour market. This module builds rows only; it estimates nothing.

Rules (PAP §4.1 H1 table, D4, D13, D14)
- **Task values.** Global `onet_task` rows of `release` / `source`, pivoted per period.
  `automation_share_all_lb` / `_ub` are computed per period with the components in
  `occupations.SUPPRESSION[release]` and the formula of the occupation table
  (lb = automation_pct * (100 - suppressed) / 100, ub = lb + suppressed; null unless every
  component is published), then averaged. Every value column is averaged by
  `two_month_mean` (D13) with `n_periods` = the number of distinct `period_start` values of
  the release and source: a month with no value is skipped, never treated as 0, and the
  task weight is the mean of the months' `pct` with unpublished = 0.
- **Occupations.** A task's candidate Task IDs are `index.task_ids_for(node_name)` and
  `int(node_id)`. Its occupations are the sorted set of `soc6 = code[:7]` over
  `occupations_for_text(node_name)` and `occupations_for(int(node_id))`, the same union as
  the occupation table (ruling R6). `n_occ` = the number of distinct soc6.
- **Families.** The union of families (D14) over the candidate Task IDs
  (`families_for_text` plus the panel `node_id`'s own links). `n_family` = their number.
- **Rows.** One row per (task, soc6, family). `weight` = task weight / (`n_occ` x
  `n_family`), so usage is conserved.
- **OEWS code and wage.** `oews_code` = `oews_code_for(soc6, oews_codes, soc_structure)`,
  possibly null. `log_wage` and `wage_status` come from the OEWS code through
  `log_wage_table`: status `"no_oews_code"` if the code is null, `"no_wage_row"` if the code
  is not in the wage table, else the wage table's status (`published`, `topcoded`,
  `suppressed`).
- **Error cost.** `error_cost` = `error_cost_indicator(soc6)` (D15).
- **Cluster codes.** `task_code` = 0-based dense integer code of `task_node` (= panel
  `node_id`); `occ_code` = 0-based dense integer code of `soc6`. The occupation cluster is
  the soc6 code: two soc6 codes that share an OEWS code are separate rows and clusters, with
  the same wage.
- **Structural drops**, in this order, each node counted once under its first reason, in
  percent of `total_weight` (the D13 weight of every global `onet_task` node of the release
  and source, `unmatched:*` included): `unmatched_task` (`node_id` starts with
  `unmatched:`), `no_occupation`, `no_family`, `zero_weight` (weight 0; no usage).
  `zero_weight` is 0% of weight by definition, so `structural_drop_nodes` also counts the
  dropped nodes per reason, in the same key order.
- **Variable-level drops** (a missing outcome, predictor or OEWS code) are not applied here.
  Each estimator applies them to its own variables.
"""

from dataclasses import dataclass, field
from typing import Literal

import polars as pl

from aideleg.aei.tasks import TaskIndex
from aideleg.bls.oews import oews_code_for
from aideleg.occupations import SUPPRESSION
from aideleg.rq1.inputs import (
    error_cost_indicator,
    families_for_text,
    log_wage_table,
    two_month_mean,
)

OUTCOME_COLUMNS = ("automation_pct", "augmentation_pct", "directive_pct", "feedback_loop_pct",
                   "task_iteration_pct", "validation_pct", "learning_pct", "ai_autonomy_mean",
                   "automation_share_all_lb", "automation_share_all_ub")
ROW_COLUMNS = ["task_node", "task_code", "soc6", "oews_code", "occ_code", "family", "weight",
               "n_occ", "n_family", *OUTCOME_COLUMNS, "human_education_years_mean", "log_wage",
               "wage_status", "error_cost"]
DROP_REASONS = ("unmatched_task", "no_occupation", "no_family", "zero_weight")

_PUBLISHED = [c for c in OUTCOME_COLUMNS if not c.startswith("automation_share_all")]
_VALUES = [*OUTCOME_COLUMNS, "human_education_years_mean"]


@dataclass(frozen=True)
class TaskRows:
    rows: pl.DataFrame
    total_weight: float
    structural_drops: dict[str, float] = field(default_factory=dict)
    structural_drop_nodes: dict[str, int] = field(default_factory=dict)
    release: str = "r6"
    source: str = "claude_ai"
    family_level: str = "iwa"


def _task_values(panel: pl.DataFrame, release: str, source: str) -> pl.DataFrame:
    """node_id, node_name, weight and the D13-averaged value columns, one row per node."""
    rel = panel.filter((pl.col("release") == release) & (pl.col("source") == source))
    n_periods = rel["period_start"].n_unique()
    comps = SUPPRESSION[release]
    metrics = ["pct", *_PUBLISHED, "human_education_years_mean", *(comps or ())]
    long = rel.filter((pl.col("geo_level") == "global") & (pl.col("taxonomy") == "onet_task")
                      & pl.col("metric").is_in(metrics))
    if long.is_empty():
        raise ValueError(f"no global onet_task rows for {release}/{source}")
    names = (long.sort("period_start").group_by("node_id")
             .agg(pl.col("node_name").drop_nulls().first()))
    wide = long.pivot(on="metric", index=["node_id", "period_start"], values="value",
                      aggregate_function=None)
    wide = wide.with_columns(pl.lit(None, pl.Float64).alias(m) for m in metrics
                             if m not in wide.columns)
    if comps is None:
        supp = pl.lit(None, pl.Float64)
    else:
        supp = pl.when(pl.all_horizontal(pl.col(c).is_not_null() for c in comps)).then(
            pl.sum_horizontal(comps))
    lb = pl.col("automation_pct") * (100 - pl.col("_supp")) / 100
    wide = (wide.with_columns(_supp=supp)
            .with_columns(automation_share_all_lb=lb)
            .with_columns(automation_share_all_ub=pl.col("automation_share_all_lb")
                          + pl.col("_supp")))
    out = two_month_mean(wide, _VALUES, key=["node_id"], n_periods=n_periods)
    return out.join(names, on="node_id", how="left")


def _candidates(node_id: str, name: str | None, index: TaskIndex,
                families: pl.DataFrame) -> tuple[list[str], list[str]]:
    """(sorted soc6 codes, sorted families) over every candidate Task ID of the node."""
    occs = set(index.occupations_for_text(name)) if name is not None else set()
    fams = set(families_for_text(name, index, families)) if name is not None else set()
    if node_id.isdigit():
        tid = int(node_id)
        occs |= set(index.occupations_for(tid))
        fams |= set(families.filter(pl.col("task_id") == tid)["family"].to_list())
    return sorted({c[:7] for c in occs}), sorted(fams)


def build_task_rows(panel: pl.DataFrame, index: TaskIndex, families: pl.DataFrame,
                    wages: pl.DataFrame, oews_codes: set[str],
                    soc_structure: pl.DataFrame | None, *, release: str = "r6",
                    source: str = "claude_ai",
                    family_level: Literal["iwa", "gwa", "dwa"] = "iwa") -> TaskRows:
    """The H1/H3 rows (see the module docstring). `families` comes from `task_families`
    at `family_level`; `wages` from `load_national_wages`."""
    tasks = _task_values(panel, release, source)
    total = float(tasks["weight"].sum())

    soc_lists, fam_lists, reasons = [], [], []
    for node_id, name, w in tasks.select("node_id", "node_name", "weight").iter_rows():
        if node_id.startswith("unmatched:"):
            occs, fams, why = [], [], "unmatched_task"
        else:
            occs, fams = _candidates(node_id, name, index, families)
            why = ("no_occupation" if not occs else "no_family" if not fams
                   else "zero_weight" if not w > 0 else None)
        soc_lists.append(occs)
        fam_lists.append(fams)
        reasons.append(why)
    tasks = tasks.with_columns(
        soc6=pl.Series(soc_lists, dtype=pl.List(pl.String)),
        family=pl.Series(fam_lists, dtype=pl.List(pl.String)),
        _reason=pl.Series(reasons, dtype=pl.String))

    dropped = tasks.group_by("_reason").agg(pl.col("weight").sum(), n=pl.len())
    by = dict(zip(dropped["_reason"], dropped["weight"], strict=True))
    nodes = dict(zip(dropped["_reason"], dropped["n"], strict=True))
    drops = {r: (float(by.get(r, 0.0)) / total * 100 if total > 0 else 0.0)
             for r in DROP_REASONS}
    drop_nodes = {r: int(nodes.get(r, 0)) for r in DROP_REASONS}

    kept = tasks.filter(pl.col("_reason").is_null()).drop("_reason", "node_name")
    kept = kept.with_columns(n_occ=pl.col("soc6").list.len().cast(pl.Int64),
                             n_family=pl.col("family").list.len().cast(pl.Int64))
    out = (kept.explode("soc6").explode("family")
           .with_columns(weight=pl.col("weight") / (pl.col("n_occ") * pl.col("n_family")))
           .rename({"node_id": "task_node"}))

    socs = sorted(set(out["soc6"]))
    oews = {s: oews_code_for(s, oews_codes, soc_structure) for s in socs}
    wage = log_wage_table(wages).rename({"soc6": "oews_code"})
    occ = (pl.DataFrame({"soc6": socs, "oews_code": [oews[s] for s in socs]},
                        schema={"soc6": pl.String, "oews_code": pl.String})
           .join(wage, on="oews_code", how="left")
           .with_columns(
               wage_status=pl.when(pl.col("oews_code").is_null()).then(pl.lit("no_oews_code"))
               .when(pl.col("wage_status").is_null()).then(pl.lit("no_wage_row"))
               .otherwise(pl.col("wage_status")),
               error_cost=error_cost_indicator(pl.Series("soc6", socs, dtype=pl.String)),
               occ_code=pl.int_range(len(socs), dtype=pl.Int64)))
    out = (out.join(occ, on="soc6", how="left")
           .with_columns(task_code=(pl.col("task_node").rank("dense") - 1).cast(pl.Int64))
           .select(ROW_COLUMNS)
           .sort("task_node", "soc6", "family"))
    return TaskRows(out, total, drops, drop_nodes, release, source, family_level)
