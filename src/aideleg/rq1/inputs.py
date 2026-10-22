"""Shared RQ1 inputs: D13 two-month averaging, wages, D14 task families, D15 error cost.

Input builders only. Nothing here relates a delegation measure to wage, education, error
cost or country. AEI data are conversations matched to O*NET tasks.
"""

from pathlib import Path
from typing import Literal

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.aei.tasks import TaskIndex
from aideleg.config import RAW

ERROR_COST_MAJOR = ("23", "29")
ERROR_COST_MINOR = ("13-2",)
ERROR_COST_CODES = ("11-3031", "41-3031")


def two_month_mean(wide: pl.DataFrame, value_cols: list[str], *, key: list[str],
                   n_periods: int) -> pl.DataFrame:
    """D13: one row per `key`.

    `weight` = sum of `pct` (null = 0) over `n_periods`. Each value is the pct-weighted mean
    over the periods where both `pct` and the value are published; null if there are none.
    A month with no value is skipped, never treated as 0.
    """
    if wide.select(key + ["period_start"]).is_duplicated().any():
        raise ValueError("duplicate (key, period_start) rows")
    n_seen = wide["period_start"].n_unique()
    if n_seen > n_periods:
        raise ValueError(f"{n_seen} distinct periods but n_periods={n_periods}")
    aggs = [(pl.col("pct").fill_null(0).sum() / n_periods).alias("weight")]
    for c in value_cols:
        ok = pl.col("pct").is_not_null() & pl.col(c).is_not_null()
        den = pl.col("pct").filter(ok).sum()
        aggs.append(pl.when(ok.any() & (den > 0)).then(
            (pl.col("pct") * pl.col(c)).filter(ok).sum() / den).alias(c))
    return wide.group_by(key).agg(aggs).sort(key)


def _tsv(path: Path) -> pl.DataFrame:
    return pl.read_csv(path, separator="\t", quote_char=None, infer_schema_length=0)


def task_families(level: Literal["iwa", "gwa", "dwa"] = "iwa", *,
                  tasks_to_dwas: Path | None = None,
                  dwa_reference: Path | None = None) -> pl.DataFrame:
    """D14: unique (`task_id`, `family`) pairs; a task with several families appears once per
    family. `iwa` = IWA ID, `gwa` = Element ID, `dwa` = DWA ID. Tasks with no DWA row are absent.
    """
    col = {"iwa": "IWA ID", "gwa": "Element ID", "dwa": "DWA ID"}[level]
    t2d = _tsv(tasks_to_dwas or RAW / by_key("onet_29_3_tasks_to_dwas").dest)
    ref = _tsv(dwa_reference or RAW / by_key("onet_29_3_dwa_reference").dest)
    ref = ref.select("DWA ID", pl.col(col).alias("family")).unique()
    multi = ref.group_by("DWA ID").len().filter(pl.col("len") > 1)
    if not multi.is_empty():
        raise ValueError(f"DWA IDs with more than one {col}: {multi['DWA ID'].to_list()[:5]}")
    out = (t2d.select(pl.col("Task ID").cast(pl.Int64).alias("task_id"), "DWA ID")
           .join(ref, on="DWA ID", how="inner")
           .select("task_id", "family")
           .drop_nulls().unique().sort("task_id", "family"))
    return out


def families_for_text(text: str, index: TaskIndex, families: pl.DataFrame,
                      level: Literal["iwa", "gwa", "dwa"] | None = None) -> list[str]:
    """Sorted, de-duplicated union of family IDs over every candidate Task ID of `text`
    (as the occupation allocation does). Empty if no candidate has a DWA link: the task is
    dropped (D14). `families` comes from `task_families`; `level` is informational."""
    ids = index.task_ids_for(text)
    if not ids:
        return []
    hit = families.filter(pl.col("task_id").is_in(ids))
    return sorted(hit["family"].unique().to_list())


def error_cost_indicator(soc6: pl.Series) -> pl.Series:
    """D15: 1 if the SOC code is legal/health (major 23, 29), financial-operations minor
    group 13-2, or one of `ERROR_COST_CODES`; else 0 (Int8)."""
    if soc6.null_count():
        raise ValueError("error_cost_indicator: null soc6")
    s = soc6.cast(pl.String)
    hit = (s.str.slice(0, 2).is_in(ERROR_COST_MAJOR) | s.str.slice(0, 4).is_in(ERROR_COST_MINOR)
           | s.is_in(ERROR_COST_CODES))
    return hit.cast(pl.Int8).alias(soc6.name)


def log_wage_table(wages: pl.DataFrame) -> pl.DataFrame:
    """`soc6, log_wage, wage_status`; log_wage is ln(a_median), null when suppressed."""
    return wages.select("soc6", log_wage=pl.col("a_median").log(),
                        wage_status=pl.col("a_median_status"))
