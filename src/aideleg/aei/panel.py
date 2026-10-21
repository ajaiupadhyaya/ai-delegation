"""The harmonised six-release AEI panel and its quality checks.

AEI data are conversations matched to O*NET tasks; nothing here says anything about jobs.

`build_panel` stacks the r1-r6 parsers into one long frame (PANEL_COLUMNS) and writes
`data/derived/aei_panel.parquet`. Cells AEI did not publish have no row; they are never
imputed. `check_panel` audits the frame and describes coverage only.

Period windows for r1 and r2 are defaults (their READMEs state none); see parse_early.
"""

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.aei.parse_early import parse_r1, parse_r2
from aideleg.aei.parse_facet import parse_facet_release
from aideleg.aei.parse_r6 import parse_r6
from aideleg.aei.schema import PANEL_COLUMNS, TAXONOMIES, is_canonical
from aideleg.aei.tasks import TaskIndex
from aideleg.config import DERIVED, RAW, RELEASES

SOURCES = {"claude_ai": "claude_ai", "api": "1p_api"}
SHARE_TOLERANCE = 0.5  # a pct sum above 100 + this fails; below 100 is unpublished mass
PATTERN_TOLERANCE = 0.1
BUCKET_TOLERANCE = 1.0
PATTERNS = ["directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct",
            "learning_pct"]
_GROUP = ["release", "period_start", "period_end", "source", "geo_level", "geo_id",
          "taxonomy", "level"]
_KEY = ["release", "period_start", "period_end", "source", "geo_level", "geo_id",
        "taxonomy", "level", "node_id", "metric"]
_NODE = _GROUP + ["node_id"]


def _path(raw: Path, key: str) -> Path:
    return raw / by_key(key).dest


def build_panel(raw: Path = RAW) -> pl.DataFrame:
    """Parse r1-r6 under `raw`, stack them, and write `DERIVED/aei_panel.parquet`."""
    index = TaskIndex.from_onet(_path(raw, "aei_onet_tasks"))
    frames = [
        parse_r1(_path(raw, "aei_r1_task_pct").parent, index),
        parse_r2(_path(raw, "aei_r2_task_pct").parent, index),
    ]
    for n in (3, 4, 5):
        for key, source in SOURCES.items():
            frames.append(parse_facet_release(_path(raw, f"aei_r{n}_{key}"), f"r{n}",
                                              source, index))
    for key, source in SOURCES.items():
        frames.append(parse_r6(_path(raw, f"aei_r6_{key}"), source, index))
    df = pl.concat([f.select(PANEL_COLUMNS) for f in frames]).sort(_KEY)
    DERIVED.mkdir(parents=True, exist_ok=True)
    df.write_parquet(DERIVED / "aei_panel.parquet")
    return df


@dataclass
class QualityReport:
    """check name -> (passed, detail). Informational checks always pass."""

    checks: dict[str, tuple[bool, str]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return all(p for p, _ in self.checks.values())

    def to_markdown(self) -> str:
        lines = [
            "# AEI panel quality checks",
            "",
            "Coverage only: AEI data are conversations matched to O*NET tasks. Nothing here "
            "says anything about jobs or the labour market.",
            "",
            f"Overall: {'PASS' if self.ok else 'FAIL'}",
            "",
            "| check | result | detail |",
            "| --- | --- | --- |",
        ]
        for name, (passed, detail) in self.checks.items():
            lines.append(f"| {name} | {'pass' if passed else 'FAIL'} | "
                         f"{detail.replace('|', '/').replace(chr(10), '; ')} |")
        return "\n".join(lines) + "\n"


def _schema_checks(df: pl.DataFrame, rep: QualityReport) -> None:
    cols_ok = df.columns == PANEL_COLUMNS
    bad_rel = sorted(set(df["release"].unique()) - set(RELEASES))
    bad_tax = sorted(set(df["taxonomy"].unique()) - TAXONOMIES)
    rep.checks["columns_and_labels"] = (
        cols_ok and not bad_rel and not bad_tax,
        f"columns match: {cols_ok}; unknown releases: {bad_rel}; unknown taxonomies: {bad_tax}")
    bad_m = sorted(m for m in df["metric"].unique() if not is_canonical(m))
    rep.checks["canonical_metrics"] = (
        not bad_m, f"{df['metric'].n_unique()} metrics; non-canonical: {bad_m[:10]}")
    dup = int(df.select(_KEY).is_duplicated().sum())
    nulls = int(df["value"].null_count())
    rep.checks["unique_keys"] = (dup == 0, f"{dup} rows share a panel key; {nulls} null values")


def _shares_sum(df: pl.DataFrame, rep: QualityReport) -> None:
    """`pct` per group sums to <= 100.5. Less than 100 is unpublished mass (suppression)."""
    s = df.filter(pl.col("metric") == "pct").group_by(_GROUP).agg(
        total=pl.col("value").sum(), n=pl.len())
    if s.is_empty():
        rep.checks["shares_sum"] = (True, "no pct rows")
        return
    over = s.filter(pl.col("total") > 100 + SHARE_TOLERANCE)
    short = s.filter(pl.col("total") < 100 - SHARE_TOLERANCE)
    mass = (100 - short["total"]) if short.height else pl.Series([0.0])
    detail = (f"{s.height} groups; max sum {s['total'].max():.2f}; {over.height} above "
              f"{100 + SHARE_TOLERANCE}; {short.height} below {100 - SHARE_TOLERANCE} "
              f"(unpublished mass: mean {mass.mean():.2f}, max {mass.max():.2f} points)")
    if over.height:
        w = over.sort("total", descending=True).row(0, named=True)
        detail += (f"; worst {w['release']} {w['source']} {w['geo_id']} {w['taxonomy']} "
                   f"level {w['level']} {w['period_start']}: {w['total']:.2f}")
    rep.checks["shares_sum"] = (over.height == 0, detail)


def _pattern_sums(df: pl.DataFrame) -> pl.DataFrame:
    """Per node: number of patterns, their sum, and the published buckets."""
    keep = df.filter(pl.col("metric").is_in([*PATTERNS, "automation_pct", "augmentation_pct"])
                     & pl.col("value").is_not_null())
    v, m = pl.col("value"), pl.col("metric")
    return keep.group_by(_NODE).agg(
        n5=m.is_in(PATTERNS).sum(),
        s5=v.filter(m.is_in(PATTERNS)).sum(),
        dfl=v.filter(m.is_in(["directive_pct", "feedback_loop_pct"])).sum(),
        auto=v.filter(m == "automation_pct").first(),
        aug=v.filter(m == "augmentation_pct").first(),
    ).filter(pl.col("n5") == 5)


def _pattern_checks(df: pl.DataFrame, rep: QualityReport) -> None:
    p = _pattern_sums(df)
    bad5 = p.filter((pl.col("s5") - 100).abs() > PATTERN_TOLERANCE)
    both = p.filter(pl.col("auto").is_not_null() & pl.col("aug").is_not_null())
    badb = both.filter((pl.col("auto") + pl.col("aug") - 100).abs() > PATTERN_TOLERANCE)
    rep.checks["pattern_partition"] = (
        bad5.is_empty() and badb.is_empty(),
        f"{p.height} nodes with all five patterns: {bad5.height} with pattern sum off 100 by "
        f"> {PATTERN_TOLERANCE}; {both.height} also carry both buckets: {badb.height} with "
        f"automation + augmentation off 100")

    r6 = p.filter((pl.col("release") == "r6") & pl.col("auto").is_not_null())
    diff = (r6["auto"] - r6["dfl"] / r6["s5"] * 100).abs() if r6.height else pl.Series([0.0])
    n_bad = int((diff > BUCKET_TOLERANCE).sum())
    rep.checks["r6_bucket_consistency"] = (
        n_bad == 0,
        f"{r6.height} r6 nodes: published automation vs renormalised directive + feedback_loop; "
        f"max abs gap {diff.max():.3f} points, mean {diff.mean():.4f}; {n_bad} nodes gap > "
        f"{BUCKET_TOLERANCE} (published value kept)")


def _info_checks(df: pl.DataFrame, rep: QualityReport) -> None:
    t = df.filter((pl.col("taxonomy") == "onet_task") & (pl.col("metric") == "pct"))
    sentinel = pl.col("node_id").is_in(["unmatched:none", "unmatched:not_classified"])
    un = t.filter(pl.col("node_id").str.starts_with("unmatched:") & ~sentinel)
    g = t.filter(pl.col("geo_id") == "GLOBAL")
    tot = g.group_by("release", "source").agg(
        total=pl.col("node_id").n_unique(), periods=pl.col("period_start").n_unique())
    per = un.filter(pl.col("geo_id") == "GLOBAL").group_by("release", "source").agg(
        n=pl.col("node_id").n_unique(), mass=pl.col("value").sum())
    j = tot.join(per, on=["release", "source"], how="left").sort("release", "source")
    parts = [
        f"{r['release']} {r['source']} {r['n'] or 0}/{r['total']} nodes, "
        f"{(r['mass'] or 0) / r['periods']:.2f}%"
        for r in j.iter_rows(named=True)
    ]
    rep.checks["unmatched_tasks"] = (
        True, "global onet_task nodes with no O*NET match (sentinels none/not_classified "
        "excluded; unmatched nodes / all nodes, mean pct mass per period): " + "; ".join(parts))
    rows = df.group_by("release", "source").len().sort("release", "source")
    rep.checks["row_counts"] = (True, "; ".join(f"{r} {s} {n}" for r, s, n in rows.iter_rows()))


def check_panel(df: pl.DataFrame) -> QualityReport:
    """Run every quality check on a panel frame."""
    rep = QualityReport()
    _schema_checks(df, rep)
    _shares_sum(df, rep)
    _pattern_checks(df, rep)
    _info_checks(df, rep)
    return rep
