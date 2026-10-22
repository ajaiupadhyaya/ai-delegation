"""RQ1 descriptive anatomy: collaboration composition and usage concentration (spec §5.2).

AEI data are conversations matched to O*NET tasks. Everything here is descriptive: no
hypothesis test, no p-value. Composition tables are computed over PUBLISHED cells only (AEI
suppresses small cells; what it leaves out is not imputed), and concentration compares
releases whose suppression regimes differ (PAP §5).

Conventions
- Global rows only. The r6 months are combined by `inputs.two_month_mean` (D13): a value
  missing in one month is averaged over the month that has it, and a task or group absent in a
  month counts as zero usage there.
- `usage_share` columns are percentages that sum to 100 over the rows the table covers.
- The five collaboration patterns are `directive`, `feedback_loop`, `task_iteration`,
  `validation`, `learning`; automation = directive + feedback_loop, augmentation = the other
  three. Each is a percentage of classified conversations, as the panel carries them.
"""

import math
from typing import Literal

import numpy as np
import polars as pl

from aideleg.exposure import oews_usage
from aideleg.occupations import occupation_table
from aideleg.rq1.inputs import two_month_mean

PATTERN_COLS = ["directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct",
                "learning_pct", "automation_pct", "augmentation_pct"]
FIVE_PATTERNS = PATTERN_COLS[:5]
EDU_METRIC = "human_education_years_mean"
EDU_EDGES = (12.0, 14.0, 16.0, 18.0)
EDU_LABELS = ("<12", "12–14", "14–16", "16–18", "≥18")
EDU_MISSING = "zero published usage"
CONCENTRATION_RELEASES: dict[str, tuple[str, ...]] = {
    "claude_ai": ("r1", "r2", "r3", "r4", "r5", "r6"),
    "1p_api": ("r3", "r4", "r5", "r6"),
}


# --- panel access ---------------------------------------------------------------------------


def _slice(panel: pl.DataFrame, release: str, source: str, taxonomy: str | None = None
           ) -> pl.DataFrame:
    sub = panel.filter((pl.col("release") == release) & (pl.col("source") == source)
                       & (pl.col("geo_level") == "global"))
    return sub if taxonomy is None else sub.filter(pl.col("taxonomy") == taxonomy)


def _wide(sub: pl.DataFrame, metrics: list[str]) -> pl.DataFrame:
    """`period_start, node_id, node_name` and one column per metric (null when absent)."""
    names = sub.group_by("node_id").agg(pl.col("node_name").first())
    rows = sub.filter(pl.col("metric").is_in(metrics))
    if rows.is_empty():
        wide = sub.select("period_start", "node_id").head(0)
    else:
        wide = rows.pivot(on="metric", index=["period_start", "node_id"], values="value",
                          aggregate_function=None)
    wide = wide.with_columns(
        [pl.lit(None, pl.Float64).alias(m) for m in metrics if m not in wide.columns])
    return wide.join(names, on="node_id", how="left")


def _n_periods(panel: pl.DataFrame, release: str, source: str) -> int:
    return _slice(panel, release, source)["period_start"].n_unique()


def _matched(wide: pl.DataFrame) -> pl.DataFrame:
    return wide.filter(~pl.col("node_id").str.starts_with("unmatched:")
                       & pl.col("pct").is_not_null())


def _wmean(col: str, w: str = "weight") -> pl.Expr:
    has = pl.col(col).is_not_null()
    den = pl.col(w).filter(has).sum()
    return pl.when(den > 0).then((pl.col(w) * pl.col(col)).filter(has).sum() / den).alias(col)


# --- composition by occupation major group --------------------------------------------------


def by_major_group(panel: pl.DataFrame, *, release: str = "r6",
                   source: str = "claude_ai") -> pl.DataFrame:
    """Published `soc_major` rows: `major, name, usage_share, *PATTERN_COLS` (D13 averaged).

    `usage_share` is the D13 weight renormalised to 100 over the published groups.
    """
    sub = _slice(panel, release, source, "soc_major")
    if sub.is_empty():
        raise ValueError(f"no global soc_major rows for {release} {source}")
    wide = _wide(sub, ["pct", *PATTERN_COLS])
    tm = two_month_mean(wide.filter(pl.col("pct").is_not_null()), PATTERN_COLS,
                        key=["node_id", "node_name"], n_periods=_n_periods(panel, release, source))
    return tm.select(
        pl.col("node_id").alias("major"), pl.col("node_name").alias("name"),
        (pl.col("weight") / pl.col("weight").sum() * 100).alias("usage_share"),
        *PATTERN_COLS).sort("major")


# --- composition by wage decile -------------------------------------------------------------


def wage_deciles(occ: pl.DataFrame, wages: pl.DataFrame) -> pl.DataFrame:
    """`soc6, decile` from employment-weighted deciles of `a_median`.

    `occ` carries `soc6, tot_emp` (OEWS employment); `wages` carries `soc6, a_median`, where a
    top-coded median is already the top-code (`load_national_wages`) and a suppressed one is
    null and excluded. Occupations are sorted ascending by wage (ties by `soc6`); each takes
    decile `clip(ceil(10 * (cum_emp - emp / 2) / total_emp), 1, 10)`.
    """
    d = (occ.select("soc6", "tot_emp").join(wages.select("soc6", "a_median"), on="soc6")
         .filter(pl.col("a_median").is_not_null() & (pl.col("tot_emp") > 0))
         .sort("a_median", "soc6"))
    total = d["tot_emp"].sum()
    mid = pl.col("tot_emp").cum_sum() - pl.col("tot_emp") / 2
    dec = (10 * mid / total).round(9).ceil().clip(1, 10).cast(pl.Int64)
    return d.select("soc6", decile=dec)


def by_wage_decile(panel: pl.DataFrame, index, wages: pl.DataFrame, national: pl.DataFrame,
                   soc_structure: pl.DataFrame | None, *, release: str = "r6",
                   source: str = "claude_ai",
                   basis: Literal["published", "tasks"] = "published") -> pl.DataFrame:
    """`decile, emp_share, usage_share, n_occ, *PATTERN_COLS`, deciles 1-10 then `decile = null`.

    Per period: `occupation_table(..., basis=basis)`, then `oews_usage`; the periods are
    combined by D13 (`two_month_mean`, weight `usage_share`). Within a decile each pattern is
    the usage-weighted mean. The final row (decile null) holds the OEWS occupations with no
    published wage. `emp_share` is the decile's share of OEWS employment (percent, over every
    occupation with published employment); `usage_share` sums to 100 over all rows.
    `basis="published"` is the D9 primary; `"tasks"` is the task-allocated basis (Plan 4).
    """
    occ = occupation_table(panel, release, index, basis=basis).filter(
        pl.col("source") == source)
    periods = sorted(occ["period_start"].unique().to_list())
    if not periods:
        raise ValueError(f"no occupation rows for {release} {source}")
    frames = []
    for p in periods:
        mapped, _ = oews_usage(occ.filter(pl.col("period_start") == p), national, soc_structure,
                               shares=PATTERN_COLS)
        frames.append(mapped.rename({"usage_share": "pct"}).with_columns(period_start=pl.lit(p)))
    avg = two_month_mean(pl.concat(frames), PATTERN_COLS, key=["soc6"], n_periods=len(periods))
    base = (national.filter(pl.col("tot_emp").is_not_null()).select("soc6", "tot_emp")
            .join(wage_deciles(national, wages), on="soc6", how="left")
            .join(avg, on="soc6", how="left")
            .with_columns(pl.col("weight").fill_null(0.0)))
    total_emp = base["tot_emp"].sum()
    out = base.group_by("decile").agg([
        (pl.col("tot_emp").sum() / total_emp * 100).alias("emp_share"),
        pl.col("weight").sum().alias("usage_share"), pl.len().cast(pl.Int64).alias("n_occ"),
        *[_wmean(c) for c in PATTERN_COLS]])
    out = out.with_columns(usage_share=pl.col("usage_share") / out["usage_share"].sum() * 100)
    if out["decile"].null_count() == 0:  # every occupation has a published wage
        out = pl.concat([out, pl.DataFrame(
            {"decile": None, "emp_share": 0.0, "usage_share": 0.0, "n_occ": 0},
            schema=out.select("decile", "emp_share", "usage_share", "n_occ").schema)],
            how="diagonal")
    return out.select("decile", "emp_share", "usage_share", "n_occ", *PATTERN_COLS).sort(
        "decile", nulls_last=True)


# --- composition by education ---------------------------------------------------------------


def education_bin(years: float | None) -> str:
    """The left-closed education bin of a `human_education_years_mean` value."""
    if years is None or (isinstance(years, float) and math.isnan(years)):
        return EDU_MISSING
    for edge, label in zip(EDU_EDGES, EDU_LABELS, strict=False):
        if years < edge:
            return label
    return EDU_LABELS[-1]


def _bin_expr(col: str) -> pl.Expr:
    e = pl.when(pl.col(col).is_null()).then(pl.lit(EDU_MISSING))
    for edge, label in zip(EDU_EDGES, EDU_LABELS, strict=False):
        e = e.when(pl.col(col) < edge).then(pl.lit(label))
    return e.otherwise(pl.lit(EDU_LABELS[-1]))


def by_education(panel: pl.DataFrame, *, release: str = "r6",
                 source: str = "claude_ai") -> pl.DataFrame:
    """`bin, usage_share, n_tasks, *PATTERN_COLS` over global matched `onet_task` rows.

    Tasks are D13 averaged, then binned on `human_education_years_mean`; a task with no value
    is `bin = "zero published usage"`: in the panel these are exactly the tasks published
    with pct 0.00 (the row's `usage_share` shows it).
    Empty bins are omitted. `usage_share` sums to 100.
    """
    sub = _slice(panel, release, source, "onet_task")
    wide = _matched(_wide(sub, ["pct", EDU_METRIC, *PATTERN_COLS]))
    if wide.is_empty():
        raise ValueError(f"no matched onet_task rows for {release} {source}")
    tm = two_month_mean(wide, [EDU_METRIC, *PATTERN_COLS], key=["node_id"],
                        n_periods=_n_periods(panel, release, source))
    order = {b: i for i, b in enumerate([*EDU_LABELS, EDU_MISSING])}
    out = (tm.with_columns(bin=_bin_expr(EDU_METRIC)).group_by("bin").agg([
        pl.col("weight").sum().alias("usage_share"), pl.len().cast(pl.Int64).alias("n_tasks"),
        *[_wmean(c) for c in PATTERN_COLS]]))
    out = out.with_columns(usage_share=pl.col("usage_share") / out["usage_share"].sum() * 100)
    return (out.with_columns(_o=pl.col("bin").replace_strict(order, return_dtype=pl.Int64))
            .sort("_o").select("bin", "usage_share", "n_tasks", *PATTERN_COLS))


# --- concentration --------------------------------------------------------------------------


def gini(shares: np.ndarray) -> float:
    """(2 Σ i·x₍ᵢ₎) / (n Σ x) − (n+1)/n, x ascending, i 1-based."""
    x = np.sort(np.asarray(shares, dtype=float))
    n = x.size
    return float(2.0 * np.sum(np.arange(1, n + 1) * x) / (n * x.sum()) - (n + 1) / n)


def lorenz_points(shares: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Lorenz curve (cumulative task fraction, cumulative usage fraction), both from 0 to 1."""
    x = np.sort(np.asarray(shares, dtype=float))
    n = x.size
    return np.arange(n + 1) / n, np.concatenate([[0.0], np.cumsum(x) / x.sum()])


def concentration_stats(shares: np.ndarray) -> dict:
    """`n_tasks, gini, top1_share, top5_share, top10_share, n_tasks_50pct` for one release.

    top-x share (percent) = usage share of the ⌈x% · n⌉ largest tasks.
    """
    x = np.sort(np.asarray(shares, dtype=float))[::-1]
    n, total = x.size, x.sum()
    cum = np.cumsum(x) / total * 100
    out = {"n_tasks": n, "gini": gini(x)}
    for pct in (1, 5, 10):
        k = max(1, math.ceil(round(pct * n / 100, 9)))
        out[f"top{pct}_share"] = float(cum[k - 1])
    out["n_tasks_50pct"] = int(np.searchsorted(cum, 50.0 - 1e-9) + 1)
    return out


def task_shares(panel: pl.DataFrame, release: str, source: str, *,
                round_dp: int | None = None, drop_zero: bool = False) -> np.ndarray:
    """Matched `onet_task` usage shares (percent, sum 100), D13 averaged over the months.

    As published by default: every published matched task is kept, including one published as
    0.00. `round_dp` rounds each month's pct to that many decimals first and `drop_zero` drops
    tasks whose usage is 0, both before renormalising (the harmonised series).
    """
    sub = _slice(panel, release, source, "onet_task")
    wide = _matched(_wide(sub, ["pct"]))
    if round_dp is not None:
        wide = wide.with_columns(pl.col("pct").round(round_dp))
    tm = two_month_mean(wide, [], key=["node_id"],
                        n_periods=_n_periods(panel, release, source))
    if drop_zero:
        tm = tm.filter(pl.col("weight") > 0)
    w = tm["weight"].to_numpy()
    return w / w.sum() * 100


_POS = ["n_zero", "n_tasks_pos", "gini_pos", "top1_share_pos", "top5_share_pos",
        "top10_share_pos"]
_SCHEMA = {"release": pl.String, "source": pl.String, "n_tasks": pl.Int64,
           "gini": pl.Float64, "top1_share": pl.Float64, "top5_share": pl.Float64,
           "top10_share": pl.Float64, "n_tasks_50pct": pl.Int64}


def _releases(panel: pl.DataFrame):
    for source, releases in CONCENTRATION_RELEASES.items():
        for release in releases:
            if not _slice(panel, release, source, "onet_task").is_empty():
                yield release, source


def concentration(panel: pl.DataFrame) -> pl.DataFrame:
    """One row per release x source present, over the published matched tasks as published:
    `release, source, n_tasks, gini, top1_share, top5_share, top10_share, n_tasks_50pct`, then
    the positive-only columns `n_zero` (tasks published as 0), `n_tasks_pos`, `gini_pos`,
    `top1_share_pos`, `top5_share_pos`, `top10_share_pos` (usage renormalised over the tasks
    with positive usage)."""
    rows = []
    for release, source in _releases(panel):
        x = task_shares(panel, release, source)
        pos = concentration_stats(x[x > 0])
        rows.append({"release": release, "source": source, **concentration_stats(x),
                     "n_zero": int((x == 0).sum()), "n_tasks_pos": pos["n_tasks"],
                     "gini_pos": pos["gini"], "top1_share_pos": pos["top1_share"],
                     "top5_share_pos": pos["top5_share"], "top10_share_pos": pos["top10_share"]})
    schema = _SCHEMA | {"n_zero": pl.Int64, "n_tasks_pos": pl.Int64, "gini_pos": pl.Float64,
                        "top1_share_pos": pl.Float64, "top5_share_pos": pl.Float64,
                        "top10_share_pos": pl.Float64}
    return pl.DataFrame(rows, schema=schema).select([*_SCHEMA, *_POS])


def harmonised_shares(panel: pl.DataFrame, release: str, source: str) -> np.ndarray:
    """`task_shares` with each month's pct rounded to 2 dp (r6's publication precision) and
    zero-usage tasks dropped, so every release is read on the same footing."""
    return task_shares(panel, release, source, round_dp=2, drop_zero=True)


def concentration_harmonised(panel: pl.DataFrame) -> pl.DataFrame:
    """Like-for-like concentration: the `concentration` columns (without the positive-only
    block) on `harmonised_shares`, one row per release x source present."""
    rows = [{"release": r, "source": s, **concentration_stats(harmonised_shares(panel, r, s))}
            for r, s in _releases(panel)]
    return pl.DataFrame(rows, schema=_SCHEMA)
