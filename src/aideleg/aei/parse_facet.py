"""Parser for AEI releases r3 (2025-09-15), r4 (2026-01-15) and r5 (2026-03-24): the facet layout.

AEI data are conversations matched to O*NET tasks; nothing here says anything about jobs.

Raw layout (one row per value): geo_id, geography, date_start, date_end, platform_and_product,
facet, level, variable, cluster_name, value. Every (facet, variable) pair is routed through
`metric_map.csv`: it is either mapped to a canonical metric or ignored with a reason, and an
unknown pair raises.

Intersection facets are named `<base>::<other>` (e.g. `onet_task::collaboration`) and their
`cluster_name` is `<base node>::<category>`, split on the last `::`. Numeric intersections
carry the bare node name (r4) or `<node>::value` (r5). The per-task collaboration shares come
from `onet_task::collaboration`, which every release r3-r5 publishes (global geography only).

Shares from category counts (collaboration, multitasking, human-only ability, use case):
- collaboration: each published pattern is renormalised over the published classified patterns
  (`none` and `not_classified` excluded); automation = directive + feedback_loop,
  augmentation = the other three; `none_pct` / `not_classified_pct` are shares of all
  conversations of the node. Null, not zero, when nothing is classified.
- Cells under the privacy threshold (15 conversations in the intersections) are folded into
  `not_classified` by AEI. An unpublished pattern gets no row; it is never set to 0.
- In intersections, an absent `none` / `not_classified` cell is an explicit 0, because the
  node's category counts reconcile exactly with its base count (checked; see
  `_explicit_zeros`). The base `collaboration` facet has no such check, so no zeros there.
- yes/no facets give the `yes` share of published `yes` + `no`; use case gives each of
  work/personal/coursework over their published sum.
"""

from pathlib import Path

import duckdb
import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex, match_tasks, normalise_task_text
from aideleg.config import RAW

MAP_PATH = Path(__file__).with_name("metric_map.csv")
DEFINITION = "collab_v2"

_PATTERNS = ["directive", "feedback_loop", "task_iteration", "validation", "learning"]
_AUTOMATION = {"directive", "feedback_loop"}
_COLLAB_CATS = set(_PATTERNS) | {"none", "not_classified"}
_YES_NO_CATS = {"yes", "no", "not_classified"}
_USE_CASES = ["work", "personal", "coursework"]
_USE_CASE_CATS = set(_USE_CASES) | {"none", "not_classified"}
_SHARE_METRICS = {"<pattern>_pct", "multitasking_pct", "human_only_ability_pct",
                  "use_case_<category>_pct"}

_SCHEMA = {
    "release": pl.String, "period_start": pl.Date, "period_end": pl.Date,
    "source": pl.String, "geo_level": pl.String, "geo_id": pl.String,
    "taxonomy": pl.String, "level": pl.Int64, "node_id": pl.String,
    "node_name": pl.String, "metric": pl.String, "value": pl.Float64,
    "definition": pl.String,
}
_GROUP = ["geo_level", "geo_id", "taxonomy", "level", "node_id", "node_name"]


def load_metric_map() -> pl.DataFrame:
    """The audited raw (facet, variable) -> (taxonomy, metric) map, one row per pair."""
    return pl.read_csv(MAP_PATH, infer_schema=False)


def _iso_map(iso: Path | None) -> dict[str, str]:
    path = iso if iso is not None else RAW / by_key("aei_geo_iso").dest
    df = pl.read_csv(path, infer_schema=False)
    return dict(zip(df["iso_alpha_2"], df["iso_alpha_3"], strict=True))


def _read(path: Path, mapped: pl.DataFrame) -> tuple[pl.DataFrame, set[tuple[str, str]]]:
    """Mapped raw rows joined to their (taxonomy, metric), plus every observed pair."""
    con = duckdb.connect()
    con.register("metric_map", mapped.to_arrow())
    con.execute("""
        CREATE TEMP TABLE raw AS SELECT * FROM read_csv($path, header=true,
            delim=',', quote='"', escape='"', nullstr='', columns={
                'geo_id': 'VARCHAR', 'geography': 'VARCHAR', 'date_start': 'DATE',
                'date_end': 'DATE', 'platform_and_product': 'VARCHAR', 'facet': 'VARCHAR',
                'level': 'BIGINT', 'variable': 'VARCHAR', 'cluster_name': 'VARCHAR',
                'value': 'DOUBLE'})
    """, {"path": str(path)})
    pairs = set(con.sql("SELECT DISTINCT facet, variable FROM raw").fetchall())
    rows = con.sql("""
        SELECT r.*, m.taxonomy, m.metric FROM raw r
        JOIN metric_map m USING (facet, variable)
    """).pl()
    return rows, pairs


def _geo(rows: pl.DataFrame, iso: dict[str, str]) -> pl.DataFrame:
    """global -> GLOBAL; country ISO-2 -> ISO-3 (else `unmatched:<raw>`); subregions ISO 3166-2."""
    country = pl.col("geo_id").replace_strict(iso, default=None)
    return rows.with_columns(
        geo_level=pl.when(pl.col("geography") == "global").then(pl.lit("global"))
        .when(pl.col("geography") == "country").then(pl.lit("country"))
        .when(pl.col("geography").is_in(["state_us", "country-state"])).then(pl.lit("subregion"))
        .otherwise(pl.lit(None)),
        geo_id=pl.when(pl.col("geography") == "global").then(pl.lit("GLOBAL"))
        .when(pl.col("geography") == "country")
        .then(pl.coalesce(country, pl.lit("unmatched:") + pl.col("geo_id")))
        .when(pl.col("geography") == "state_us").then(pl.lit("US-") + pl.col("geo_id"))
        .otherwise(pl.col("geo_id")),
    )


def _split(rows: pl.DataFrame) -> pl.DataFrame:
    """base node text and category: intersections split on the last `::`."""
    cross = pl.col("facet").str.contains("::", literal=True)
    has = pl.col("cluster_name").str.contains("::", literal=True)
    left = pl.col("cluster_name").str.replace(r"::[^:]*$", "")
    right = pl.col("cluster_name").str.extract(r"::([^:]*)$", 1)
    cat = pl.when(cross).then(pl.when(has).then(right).otherwise(pl.lit("")))
    cat = cat.otherwise(pl.col("cluster_name"))
    base = pl.when(cross & has).then(left).otherwise(pl.col("cluster_name"))
    return rows.with_columns(
        base=base,
        category=cat.str.to_lowercase().str.replace_all(" ", "_"),
    )


def _nodes(rows: pl.DataFrame, index: TaskIndex) -> pl.DataFrame:
    """node_id: `overall`; O*NET Task ID string or `unmatched:<text>`; request text as is."""
    names = rows.filter(pl.col("taxonomy") == "onet_task")["base"].unique().drop_nulls()
    m = match_tasks(names, index)
    ids = {
        n: str(t) if t is not None else f"unmatched:{normalise_task_text(n)}"
        for n, t in zip(m["task_name"], m["task_id"], strict=True)
    }
    tax = pl.col("taxonomy")
    return rows.with_columns(
        node_id=pl.when(tax == "overall").then(pl.lit("overall"))
        .when(tax == "onet_task").then(pl.col("base").replace_strict(ids, default=None))
        .otherwise(pl.col("base")),
        node_name=pl.when(tax == "overall").then(pl.lit("overall")).otherwise(pl.col("base")),
        level=pl.when(tax == "request").then(pl.col("level")).otherwise(pl.lit(0)),
    )


def _check_categories(rows: pl.DataFrame, metric: str, allowed: set[str]) -> None:
    bad = set(rows.filter(pl.col("metric") == metric)["category"].unique()) - allowed
    if bad:
        raise ValueError(f"unexpected categories for {metric}: {sorted(bad)}")


def _collab(rows: pl.DataFrame) -> pl.DataFrame:
    c = rows.filter(pl.col("metric") == "<pattern>_pct")
    _check_categories(c, "<pattern>_pct", _COLLAB_CATS)
    classified = pl.col("category").is_in(_PATTERNS)
    c = c.with_columns(
        cls=pl.col("value").filter(classified).sum().over(_GROUP),
        total=pl.col("value").sum().over(_GROUP),
    )
    shares = c.select(
        *_GROUP,
        metric=pl.col("category") + "_pct",
        value=pl.when(classified).then(pl.col("value") / pl.col("cls") * 100)
        .otherwise(pl.col("value") / pl.col("total") * 100),
    )
    buckets = c.group_by(_GROUP).agg(
        auto=pl.col("value").filter(pl.col("category").is_in(list(_AUTOMATION))).sum(),
        cls=pl.col("value").filter(classified).sum(),
    )
    ok = pl.col("cls") > 0
    auto = pl.when(ok).then(pl.col("auto") / pl.col("cls") * 100).otherwise(pl.lit(None))
    aug = pl.when(ok).then((pl.col("cls") - pl.col("auto")) / pl.col("cls") * 100)
    buckets = pl.concat([
        buckets.select(*_GROUP, metric=pl.lit("automation_pct"), value=auto),
        buckets.select(*_GROUP, metric=pl.lit("augmentation_pct"),
                       value=aug.otherwise(pl.lit(None))),
    ])
    return pl.concat([shares, buckets, _explicit_zeros(rows, c)])


def _explicit_zeros(rows: pl.DataFrame, c: pl.DataFrame) -> pl.DataFrame:
    """`none_pct` / `not_classified_pct` = 0 where an intersection node publishes no such cell.

    These zeros are derived from the published totals, not imputed: for every intersection
    node the category counts must sum exactly to the node's base count (`onet_task_count` or
    `request_count`, same geography and level), which holds on all r3-r5 files. When they
    do, an absent `none` or `not_classified` cell means no conversations, so 0 is a
    published fact. A mismatch raises; a node with no base count gets no zero rows.
    """
    cross = c.filter(pl.col("facet").str.contains("::", literal=True))
    sums = cross.group_by(_GROUP).agg(
        s=pl.col("value").sum(),
        has_none=(pl.col("category") == "none").any(),
        has_nc=(pl.col("category") == "not_classified").any(),
    )
    base = rows.filter((pl.col("metric") == "count") & pl.col("taxonomy").is_in(
        ["onet_task", "request"])).select(*_GROUP, base=pl.col("value"))
    j = sums.join(base, on=_GROUP, how="left")
    bad = j.filter(pl.col("base").is_not_null() & ((pl.col("s") - pl.col("base")).abs() > 1e-6))
    if bad.height:
        r = bad.row(0, named=True)
        raise ValueError(f"collaboration counts for {r['node_name']!r} sum to {r['s']}, "
                         f"base count is {r['base']}: {bad.height} nodes do not reconcile")
    ok = j.filter(pl.col("base").is_not_null())
    return pl.concat([
        ok.filter(~pl.col("has_none")).select(*_GROUP, metric=pl.lit("none_pct"),
                                              value=pl.lit(0.0)),
        ok.filter(~pl.col("has_nc")).select(*_GROUP, metric=pl.lit("not_classified_pct"),
                                            value=pl.lit(0.0)),
    ])


def _category_shares(rows: pl.DataFrame, metric: str, targets: list[str],
                     classified: list[str], allowed: set[str], name: pl.Expr) -> pl.DataFrame:
    """Share of each published target category over the published `classified` ones."""
    c = rows.filter(pl.col("metric") == metric)
    _check_categories(c, metric, allowed)
    c = c.with_columns(cls=pl.col("value").filter(pl.col("category").is_in(classified)).sum()
                       .over(_GROUP))
    return c.filter(pl.col("category").is_in(targets)).select(
        *_GROUP, metric=name, value=pl.col("value") / pl.col("cls") * 100,
    )


def _direct(rows: pl.DataFrame) -> pl.DataFrame:
    d = rows.filter(~pl.col("metric").is_in(list(_SHARE_METRICS)))
    # numeric intersections: bare node (r4) or `<node>::value` (r5); nothing else is mapped
    cross = pl.col("facet").str.contains("::", literal=True)
    bad = d.filter(cross & ~pl.col("category").is_in(["", "value"]))
    if bad.height:
        raise ValueError(f"unexpected intersection suffix: {bad['cluster_name'][0]!r}")
    return d.select(*_GROUP, "metric", "value")


def parse_facet_release(
    path: Path, release: str, source: str, index: TaskIndex, iso: Path | None = None,
) -> pl.DataFrame:
    """One r3/r4/r5 raw file -> PANEL_COLUMNS. `source` is `claude_ai` or `1p_api`.

    `definition` is `collab_v2|<platform_and_product>`; the period is the file's
    date_start/date_end as published. Raises ValueError on any (facet, variable) that
    `metric_map.csv` does not list for this release.
    """
    mm = load_metric_map().filter(
        pl.col("release_set").str.split(";").list.contains(pl.lit(release)))
    rows, pairs = _read(path, mm.filter(pl.col("action") == "map")
                        .select("facet", "variable", "taxonomy", "metric"))
    known = set(mm.select("facet", "variable").iter_rows())
    unknown = sorted(pairs - known)
    if unknown:
        raise ValueError(f"{release}: unmapped (facet, variable) pairs {unknown[:10]}")
    platforms = rows["platform_and_product"].unique().to_list()
    starts, ends = rows["date_start"].unique(), rows["date_end"].unique()
    if len(platforms) != 1 or len(starts) != 1 or len(ends) != 1:
        raise ValueError(f"{release}: expected one platform and period, got {platforms}")

    rows = _nodes(_split(_geo(rows, _iso_map(iso))), index)
    out = pl.concat([
        _direct(rows),
        _collab(rows),
        _category_shares(rows, "multitasking_pct", ["yes"], ["yes", "no"],
                         _YES_NO_CATS, pl.lit("multitasking_pct")),
        _category_shares(rows, "human_only_ability_pct", ["yes"], ["yes", "no"],
                         _YES_NO_CATS, pl.lit("human_only_ability_pct")),
        _category_shares(rows, "use_case_<category>_pct", _USE_CASES, _USE_CASES,
                         _USE_CASE_CATS,
                         "use_case_" + pl.col("category") + "_pct"),
    ], how="vertical_relaxed")
    out = out.with_columns(
        release=pl.lit(release), period_start=pl.lit(starts[0]), period_end=pl.lit(ends[0]),
        source=pl.lit(source), definition=pl.lit(f"{DEFINITION}|{platforms[0]}"),
    ).select(PANEL_COLUMNS).cast(_SCHEMA)
    key = ["geo_level", "geo_id", "taxonomy", "level", "node_id", "metric"]
    if out.select(key).is_duplicated().any():
        raise ValueError(f"{release}: duplicate panel keys")
    if out["geo_level"].null_count() or out["node_id"].null_count():
        raise ValueError(f"{release}: unresolved geography or node")
    return out
