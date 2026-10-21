"""Parser for AEI release r6 (2026-06-26): calendar-month files in the long metric layout.

AEI data are conversations matched to O*NET tasks; nothing here says anything about jobs.

Raw layout (one row per value): date_start, date_end, geo_id, geo_level, category_name,
hierarchy_level, metric_id, value, node_name, node_external_id. Each file holds two calendar
months (April and May 2026); every month is its own period with `release = "r6"`.
`date_end` is exclusive, as published.

Taxonomy by (category_name, hierarchy_level):
  onet 0/1/2/3 -> onet_task/onet_dwa/onet_iwa/onet_gwa, soc_occupation 0/1 -> soc_detailed/
  soc_major, request -> request (level kept), overall -> overall. Outside `request`, `level`
  is 0 because the taxonomy already names the level.

Node ids:
- onet_task: the O*NET Task ID. `node_external_id` at level 0 is the Task ID (checked on the
  real files). It is used when the index knows it. The statement wording drifts between O*NET
  versions (commas, word order) so the ID wins over the text; a Task ID the index does not
  know falls back to the text match, then to `unmatched:<normalised text>`.
- onet_dwa/iwa/gwa: the O*NET element ID; soc_detailed: the SOC code (`13-2061.00`);
  soc_major: the two-digit group; request: the topic UUID; overall: `overall`.

Metrics:
- `collaboration_bucket_automation_pct` -> `automation_pct`, `..._augmentation_pct` ->
  `augmentation_pct`, kept as published (they are already shares of the five classified
  patterns; the quality check confirms they equal directive + feedback_loop).
- `collaboration_<pattern>_pct` is published as a share of ALL conversations (the five
  patterns plus `none` sum to 100), so, as in r3-r5, each pattern is renormalised over the
  published classified patterns; `collaboration_none_pct` -> `none_pct` stays a share of all.
- `artifact_<label>_pct` is kept under its own name. Every other metric is canonical as
  published. An unmapped `metric_id` raises.
- `usage_pct` for subregions is a share of the parent country, as published; it is not
  rescaled.

r6 publishes no `not_classified_pct` (only `collaboration_none_pct`), so `none_pct` here is a
share of conversations whose denominator differs slightly from r3-r5, where AEI folds
suppressed cells into `not_classified`.

Rows are never imputed: a cell AEI did not publish has no row.
"""

from pathlib import Path

import duckdb
import polars as pl

from aideleg.aei.schema import PANEL_COLUMNS, is_canonical
from aideleg.aei.tasks import TaskIndex, match_tasks, normalise_task_text

DEFINITION = "collab_v2"

_TAXONOMY = {
    ("overall", 0): "overall",
    ("onet", 0): "onet_task", ("onet", 1): "onet_dwa",
    ("onet", 2): "onet_iwa", ("onet", 3): "onet_gwa",
    ("soc_occupation", 0): "soc_detailed", ("soc_occupation", 1): "soc_major",
    ("request", 0): "request", ("request", 1): "request", ("request", 2): "request",
}
_PATTERNS = ["directive", "feedback_loop", "task_iteration", "validation", "learning"]
_PATTERN_METRICS = {f"collaboration_{p}_pct": f"{p}_pct" for p in _PATTERNS}
_RENAMED = {
    **_PATTERN_METRICS,
    "collaboration_bucket_automation_pct": "automation_pct",
    "collaboration_bucket_augmentation_pct": "augmentation_pct",
    "collaboration_none_pct": "none_pct",
}
_SOURCES = {"claude_ai", "1p_api"}
_NODE = ["period_start", "period_end", "geo_level", "geo_id", "taxonomy", "level",
         "node_id", "node_name"]
_SCHEMA = {
    "release": pl.String, "period_start": pl.Date, "period_end": pl.Date,
    "source": pl.String, "geo_level": pl.String, "geo_id": pl.String,
    "taxonomy": pl.String, "level": pl.Int64, "node_id": pl.String,
    "node_name": pl.String, "metric": pl.String, "value": pl.Float64,
    "definition": pl.String,
}


def _read(path: Path) -> pl.DataFrame:
    con = duckdb.connect()
    return con.sql("""
        SELECT date_start AS period_start, date_end AS period_end, geo_id, geo_level,
               category_name, hierarchy_level, metric_id, value, node_name, node_external_id
        FROM read_csv(?, header=true, delim=',', quote='"', escape='"', nullstr='',
            columns={'date_start': 'DATE', 'date_end': 'DATE', 'geo_id': 'VARCHAR',
                      'geo_level': 'VARCHAR', 'category_name': 'VARCHAR',
                      'hierarchy_level': 'BIGINT', 'metric_id': 'VARCHAR',
                      'value': 'DOUBLE', 'node_name': 'VARCHAR',
                      'node_external_id': 'VARCHAR'})
        WHERE value IS NOT NULL
    """, params=[str(path)]).pl()


def _task_ids(raw: pl.DataFrame, index: TaskIndex) -> dict[str, str]:
    """external task id -> node_id for every onet level-0 node."""
    uniq = raw.filter((pl.col("category_name") == "onet") & (pl.col("hierarchy_level") == 0)
                      ).select("node_external_id", "node_name").unique()
    texts = match_tasks(uniq["node_name"], index)
    out: dict[str, str] = {}
    for ext in uniq["node_external_id"]:
        if ext is not None and ext.isdigit() and index.has_task_id(int(ext)):
            out[ext] = str(int(ext))
    taken = set(out.values())
    for ext, name, by_text in zip(uniq["node_external_id"], uniq["node_name"],
                                  texts["task_id"], strict=True):
        if ext in out:
            continue
        # a text fallback may not land on an ID that r6 publishes under its own node (the
        # same statement can carry several Task IDs): that stays a separate, unmatched node
        if by_text is not None and str(by_text) not in taken:
            out[ext] = str(by_text)
            taken.add(str(by_text))
        else:
            out[ext] = f"unmatched:{normalise_task_text(name)}"
    return out


def _prepare(raw: pl.DataFrame, index: TaskIndex) -> pl.DataFrame:
    keys = pl.DataFrame({
        "category_name": [k[0] for k in _TAXONOMY], "hierarchy_level": [k[1] for k in _TAXONOMY],
        "taxonomy": list(_TAXONOMY.values()),
    }, schema={"category_name": pl.String, "hierarchy_level": pl.Int64, "taxonomy": pl.String})
    rows = raw.join(keys, on=["category_name", "hierarchy_level"], how="left")
    if rows["taxonomy"].null_count():
        bad = rows.filter(pl.col("taxonomy").is_null()).select(
            "category_name", "hierarchy_level").unique().rows()
        raise ValueError(f"r6: unmapped (category, level) {bad}")
    metric = pl.col("metric_id").replace(_RENAMED)
    rows = rows.with_columns(metric=metric)
    unknown = sorted(m for m in rows["metric"].unique() if not is_canonical(m))
    if unknown:
        raise ValueError(f"r6: unmapped metric_id values {unknown[:10]}")
    ids = _task_ids(raw, index)
    tax = pl.col("taxonomy")
    return rows.with_columns(
        node_id=pl.when(tax == "overall").then(pl.lit("overall"))
        .when(tax == "onet_task").then(pl.col("node_external_id").replace_strict(ids, default=None))
        .otherwise(pl.col("node_external_id")),
        node_name=pl.when(tax == "overall").then(pl.lit("overall"))
        .otherwise(pl.col("node_name")),
        level=pl.when(tax == "request").then(pl.col("hierarchy_level")).otherwise(pl.lit(0)),
    )


def _renormalise(rows: pl.DataFrame) -> pl.DataFrame:
    """Each pattern over the published classified patterns of its node and period.

    When every pattern is 0 (all conversations are `none`) no share is defined: null, not 0.
    """
    is_pat = pl.col("metric").is_in(list(_PATTERN_METRICS.values()))
    total = pl.col("value").filter(is_pat).sum().over(_NODE)
    share = pl.when(total > 0).then(pl.col("value") / total * 100)  # else null, as in r2
    return rows.with_columns(value=pl.when(is_pat).then(share).otherwise(pl.col("value")))


def parse_r6(path: Path, source: str, index: TaskIndex) -> pl.DataFrame:
    """One r6 raw file -> PANEL_COLUMNS. `source` is `claude_ai` or `1p_api`."""
    if source not in _SOURCES:
        raise ValueError(f"unknown source {source!r}")
    rows = _renormalise(_prepare(_read(path), index))
    levels = set(rows["geo_level"].unique())
    if not levels <= {"global", "country", "subregion"}:
        raise ValueError(f"r6: unexpected geo_level {levels}")
    out = rows.with_columns(
        release=pl.lit("r6"), source=pl.lit(source), definition=pl.lit(DEFINITION),
    ).select(PANEL_COLUMNS).cast(_SCHEMA)
    key = ["period_start", "geo_level", "geo_id", "taxonomy", "level", "node_id", "metric"]
    if out.select(key).is_duplicated().any():
        raise ValueError("r6: duplicate panel keys")
    if out["node_id"].null_count():
        raise ValueError("r6: unresolved node")
    return out
