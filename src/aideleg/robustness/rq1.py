"""H1/H3 robustness pieces (Plan 4 Task 11): the records of a Plan 2 `HypothesisResult`, the
H3 validation bounds (R10) and the Consequence-of-Error column (R27). H2 pieces (Task 12): the
record of a Plan 2 H2 result (`h2_records`) and the within-r6 April vs May check (`within_r6`,
R37), which is Plan 4's own code.

Everything else (rows, estimators, inference) is Plan 2's, through `upstream`. The only new
RQ1 constructions are `validation_bounds` (PAP §11 C-57) and `with_coe` (C-58).

AEI data are conversations matched to O*NET tasks. H1 and H3 describe how tasks differ,
weighted by the occupations they are allocated to; they do not compare workers.
"""

import dataclasses
import math
from fractions import Fraction

import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy import stats

from aideleg.occupations import SUPPRESSION
from aideleg.robustness import report, upstream
from aideleg.robustness.inputs import consequence_of_error
from aideleg.robustness.upstream import HypothesisResult, TaskRows

RQ1_UNIT = "pp of the outcome share per unit of the regressor"
AUTONOMY_UNIT = "ai_autonomy_mean scale points per unit of the regressor"
NULL = "coefficient = 0"
R23_DISAGREE = "the two delegation measures named in H1 disagree"
R23_ALPHA = 0.05
H2_ESTIMAND = "beta (pp per year)"
H2_AUTONOMY_ESTIMAND = "beta (ai_autonomy_mean scale points per year)"  # PAP §11 C-79
H2_UNIT = "pp of the outcome share per year"
H2_AUTONOMY_UNIT = "ai_autonomy_mean scale points per year"
H2_NULL = "β = 0"
H2_ALPHA = 0.0125  # D22: H2 alone at α = 0.0125
R37_ESTIMAND = "May minus April (pp)"
R37_NULL = "May minus April = 0"

__all__ = [
    "AUTONOMY_UNIT",
    "H2_AUTONOMY_ESTIMAND",
    "H2_AUTONOMY_UNIT",
    "H2_ESTIMAND",
    "H2_UNIT",
    "R37_ESTIMAND",
    "R23_DISAGREE",
    "RQ1_UNIT",
    "consequence_of_error",
    "h2_meets_rule",
    "h2_records",
    "r23_disagrees",
    "rq1_records",
    "validation_bounds",
    "with_coe",
    "with_validation_bounds",
    "within_r6",
]


def _dropped(res: HypothesisResult) -> str:
    """Non-zero drop shares (% of total task usage), structural then variable-level."""
    return "; ".join(f"{k} {v:.2f}%" for k, v in res.drops.items() if v and v > 0)


def _p_iu(ps: list[float]) -> float:
    """D17: max of the p-values; NaN if any is NaN."""
    return math.nan if any(math.isnan(p) for p in ps) else max(ps)


def rq1_records(
    row_id: str,
    part: str,
    res: HypothesisResult,
    *,
    label: str = "robustness",
    se_key: str | None = None,
) -> list[dict]:
    """Records in `report.ROBUSTNESS_COLUMNS`: one per coefficient of `res.coefs` and, for H1,
    one more, `p_H1`. `scale` is the SE, `stat` = estimate/SE, `p` two-sided, the CI 95%.

    With `se_key="se_oneway_occ"` (R38) the SE and p are Plan 2's one-way occupation-cluster
    diagnostics (`se_oneway_occ`, `p_oneway_occ`), df = G_occ − 1, and the CI is
    estimate ± t(0.975, G_occ − 1)·SE; p_H1 is then the D17 max of those p-values."""
    unit = AUTONOMY_UNIT if res.outcome == "ai_autonomy_mean" else RQ1_UNIT
    d = res.diagnostics
    clusters = f"G_occ {d.get('g_occ', res.sample.get('g_occ'))}, " + (
        f"G_task {d.get('g_task', res.sample.get('g_task'))}"
    )
    psd = list(res.notes)
    base = {
        "row_id": row_id,
        "part": part,
        "variant": f"outcome={res.outcome}",
        "applies_to": res.hypothesis,
        "label": label,
        "unit": unit,
        "null": NULL,
        "crit_0025": None,
        "crit_005": None,
        "n": int(res.sample["n_rows"]),
        "n_dropped": None,
        "dropped": _dropped(res),
    }
    out: list[dict] = []
    ps: list[float] = []
    for name, c in res.coefs.items():
        if se_key is None:
            se, p, lo, hi, df = c.se, c.p, c.ci_low, c.ci_high, c.df
            how = "two-way cluster (occupation, task)"
        else:
            if se_key != "se_oneway_occ":
                raise ValueError(f"unknown se_key {se_key!r}")
            df = int(d["g_occ"]) - 1
            se = float(d["se_oneway_occ"][name])
            p = float(d["p_oneway_occ"][name])
            half = float(stats.t.ppf(0.975, df)) * se
            lo, hi = c.estimate - half, c.estimate + half
            how = "one-way cluster by occupation (R38)"
        ps.append(p)
        note = "; ".join([f"SE {how}", f"df {df}", clusters, *psd])
        out.append(
            base
            | {
                "estimand": name,
                "estimate": c.estimate,
                "scale": se,
                "ci_lo": lo,
                "ci_hi": hi,
                "stat": c.estimate / se,
                "p": p,
                "note": note,
            }
        )
    if res.hypothesis == "H1":
        p_h1 = res.p_family if se_key is None else _p_iu(ps)
        out.append(
            base
            | {
                "estimand": "p_H1",
                "unit": None,
                "null": "β_e = 0 or β_w = 0",
                "estimate": None,
                "scale": None,
                "ci_lo": None,
                "ci_hi": None,
                "stat": None,
                "p": p_h1,
                "note": "p_H1 = max(p_educ, p_wage), the intersection-union p (D17)"
                + ("; from the one-way occupation-cluster p-values" if se_key else ""),
            }
        )
    for r in out:
        report.check_record(r)
    return out


def r23_disagrees(res: HypothesisResult, primary: dict[str, float]) -> bool:
    """PAP §4.1: every tested H1 coefficient of the R23 fit has the sign opposite to the
    primary (`automation_pct`) coefficient and p < 0.05 (nominal)."""
    names = list(primary)
    if not names:
        return False
    for n in names:
        c = res.coefs[n]
        if not (c.estimate * primary[n] < 0 and c.p < R23_ALPHA):
            return False
    return True


def validation_bounds(panel: pl.DataFrame, *, release: str, source: str) -> pl.DataFrame:
    """`task_node, validation_share_all_lb, validation_share_all_ub` (PAP §11 C-57).

    Per period, lb = v·(100 − s)/100 and ub = lb + s, with v = `validation_pct` and s the sum
    of the release's `occupations.SUPPRESSION` components (null unless every component is
    published); then the D13 `two_month_mean` over the release's periods, as Plan 2 does for
    the automation bounds (C-4)."""
    rel = panel.filter((pl.col("release") == release) & (pl.col("source") == source))
    n_periods = rel["period_start"].n_unique()
    comps = SUPPRESSION[release]
    metrics = ["pct", "validation_pct", *(comps or ())]
    long = rel.filter(
        (pl.col("geo_level") == "global")
        & (pl.col("taxonomy") == "onet_task")
        & pl.col("metric").is_in(metrics)
    )
    if long.is_empty():
        raise ValueError(f"no global onet_task rows for {release}/{source}")
    wide = long.pivot(
        on="metric", index=["node_id", "period_start"], values="value", aggregate_function=None
    )
    wide = wide.with_columns(
        pl.lit(None, pl.Float64).alias(m) for m in metrics if m not in wide.columns
    )
    if comps is None:
        supp = pl.lit(None, pl.Float64)
    else:
        supp = pl.when(pl.all_horizontal(pl.col(c).is_not_null() for c in comps)).then(
            pl.sum_horizontal(comps)
        )
    wide = (
        wide.with_columns(_supp=supp)
        .with_columns(
            validation_share_all_lb=pl.col("validation_pct") * (100 - pl.col("_supp")) / 100
        )
        .with_columns(validation_share_all_ub=pl.col("validation_share_all_lb") + pl.col("_supp"))
    )
    cols = ["validation_share_all_lb", "validation_share_all_ub"]
    out = upstream.two_month_mean(wide, cols, key=["node_id"], n_periods=n_periods)
    return out.select(pl.col("node_id").alias("task_node"), *cols)


def with_validation_bounds(tr: TaskRows, bounds: pl.DataFrame) -> TaskRows:
    """`tr` with the bound columns left-joined on `task_node`."""
    return dataclasses.replace(tr, rows=tr.rows.join(bounds, on="task_node", how="left"))


def with_coe(tr: TaskRows, coe: pl.DataFrame) -> TaskRows:
    """`tr` with `coe`: the soc6 Consequence-of-Error value z-scored across the distinct soc6
    codes of `tr.rows` that have a value (population SD; PAP §11 C-58). A row without a value
    keeps a null `coe`, which `estimate_h3` drops and reports as `missing_coe`."""
    occ = (
        pl.DataFrame({"soc6": tr.rows["soc6"].unique()})
        .join(coe.select("soc6", "coe"), on="soc6", how="inner")
        .drop_nulls("coe")
    )
    v = occ["coe"]
    mu, sd = v.mean(), v.std(ddof=0)
    if occ.height < 2 or not sd or sd <= 0:
        raise ValueError("Consequence of Error has no variation across the sample occupations")
    z = occ.select("soc6", coe=(pl.col("coe") - mu) / sd)
    rows = tr.rows.drop("coe", strict=False).join(z, on="soc6", how="left", maintain_order="left")
    return dataclasses.replace(tr, rows=rows)


# --- Task 12: H2 ----------------------------------------------------------------------------


def _at_most(p: float, alpha: float = H2_ALPHA) -> bool:
    """p ≤ α compared exactly on the printed decimals (PAP §11 C-24); False if p is not
    finite."""
    p = float(p)
    return math.isfinite(p) and Fraction(repr(p)) <= Fraction(repr(alpha))


def h2_meets_rule(res: HypothesisResult) -> bool:
    """Mechanically, whether the D22 rule's conditions hold: task-clustered p ≤ 0.0125, the
    release-level wild bootstrap p ≤ 0.0125 and β > 0. Not a decision for a robustness row."""
    c = res.coefs["trend"]
    return _at_most(res.p_family) and _at_most(res.diagnostics["p_wild"]) and c.estimate > 0


def h2_records(row_id: str, part: str, res: HypothesisResult, *, label: str) -> list[dict]:
    """One record in `report.ROBUSTNESS_COLUMNS` for a Plan 2 H2 result: β of the trend, its
    task-clustered SE (`scale`), 95% CI and p (`res.p_family`); the note gives the
    release-level wild bootstrap p, the 6^k weight vectors and the mechanical rule check."""
    if res.hypothesis != "H2":
        raise ValueError(f"h2_records needs an H2 result, got {res.hypothesis}")
    c = res.coefs["trend"]
    d = res.diagnostics
    releases = list(res.sample["releases"])
    k, n_draws = len(releases), int(d["n_wild_draws"])
    if 6**k != n_draws:
        raise ValueError(f"{n_draws} wild draws for {k} releases; expected 6^{k} = {6**k}")
    n_extreme = round(float(d["p_wild"]) * n_draws)
    autonomy = res.outcome == "ai_autonomy_mean"
    parts = [
        f"wild-bootstrap p = {report.fmt_p(d['p_wild'])}; weight vectors = 6^{k} = {n_draws}; "
        "would meet the H2 rule (both p <= 0.0125 and beta > 0): "
        f"{'yes' if h2_meets_rule(res) else 'no'}; not a decision",
        f"{n_extreme} of the {n_draws} weight vectors at least as extreme as the observed t",
        f"SE clustered by task, df {c.df}, G_task {d.get('g_task', res.sample.get('n_tasks'))}",
        f"release-label randomisation p = {report.fmt_p(d['p_release_label'])} over "
        f"{d['n_release_orderings']} orderings (descriptive)",
    ]
    if "r6" in res.coefs:
        r6 = res.coefs["r6"]
        parts.append(
            f"r6 indicator {report.fmt_pp(r6.estimate)} (SE {report.fmt_pp(r6.se)}, "
            f"p {report.fmt_p(r6.p)})"
        )
    rec = {
        "row_id": row_id,
        "part": part,
        "variant": f"outcome={res.outcome}; releases={','.join(releases)}",
        "applies_to": "H2",
        "label": label,
        "estimand": H2_AUTONOMY_ESTIMAND if autonomy else H2_ESTIMAND,
        "unit": H2_AUTONOMY_UNIT if autonomy else H2_UNIT,
        "estimate": c.estimate,
        "scale": c.se,
        "ci_lo": c.ci_low,
        "ci_hi": c.ci_high,
        "stat": c.estimate / c.se,
        "p": res.p_family,
        "null": H2_NULL,
        "crit_0025": None,
        "crit_005": None,
        "n": int(res.sample["n_rows"]),
        "n_dropped": None,
        "dropped": "",
        "note": "; ".join(parts),
    }
    report.check_record(rec)
    return [rec]


def within_r6(
    panel: pl.DataFrame, metric: str = "automation_pct", *, source: str = "claude_ai"
) -> dict:
    """R37 (PAP §8.2, P19): the within-task change in `metric` between the two r6 months.

    Global `onet_task` rows of r6 `source` (`unmatched:*` excluded), April t = 0 and May
    t = 1; tasks with a published `metric` in both months; weight = the task's mean `pct` over
    the two months (unpublished = 0, as D13), fixed across the months, and tasks of zero weight
    are left out (they carry no weight in the fit). WLS of `metric` on [t, task dummies], SEs
    clustered by task (`cov_type="cluster"`, `use_t=True`, t with G_task − 1 df), as H2's
    primary call. Descriptive; no wild bootstrap."""
    rel = panel.filter(
        (pl.col("release") == "r6")
        & (pl.col("source") == source)
        & (pl.col("geo_level") == "global")
        & (pl.col("taxonomy") == "onet_task")
        & pl.col("metric").is_in(["pct", metric])
        & ~pl.col("node_id").str.starts_with("unmatched:")
    )
    periods = sorted(rel["period_start"].unique().to_list())
    if len(periods) != 2 or [p.month for p in periods] != [4, 5]:
        raise ValueError(f"r6 {source} needs the April and May periods, got {periods}")
    wide = rel.pivot(
        on="metric", index=["node_id", "period_start"], values="value", aggregate_function=None
    )
    wide = wide.with_columns(
        pl.lit(None, pl.Float64).alias(m) for m in ("pct", metric) if m not in wide.columns
    )
    weight = wide.group_by("node_id").agg((pl.col("pct").fill_null(0).sum() / 2).alias("w"))
    both = (
        wide.filter(pl.col(metric).is_not_null())
        .group_by("node_id")
        .agg(pl.col("period_start").n_unique().alias("n"))
        .filter(pl.col("n") == 2)
        .join(weight, on="node_id", how="left")
    )
    n_zero = both.filter(pl.col("w") <= 0).height
    keep = both.filter(pl.col("w") > 0).select("node_id", "w")
    df = (
        wide.join(keep, on="node_id", how="inner")
        .filter(pl.col(metric).is_not_null())
        .sort("node_id", "period_start")
    )
    if keep.height < 2:
        raise ValueError(f"within_r6 needs at least two tasks, got {keep.height}")
    task = np.unique(df["node_id"].to_numpy(), return_inverse=True)[1].ravel()
    g = int(task.max()) + 1
    t = (df["period_start"] == periods[1]).cast(pl.Float64).to_numpy()
    dummies = (task[:, None] == np.arange(g)).astype(float)
    y = df[metric].cast(pl.Float64).to_numpy()
    fit = sm.WLS(y, np.column_stack([t, dummies]), weights=df["w"].to_numpy()).fit(
        cov_type="cluster", cov_kwds={"groups": task}, use_t=True
    )
    dof = int(fit.df_resid_inference)
    if dof != g - 1:
        raise AssertionError(f"df_resid_inference {dof} != G_task - 1 = {g - 1}")
    ci = np.asarray(fit.conf_int(alpha=0.05))
    return {
        "estimate": float(fit.params[0]),
        "se": float(fit.bse[0]),
        "ci_lo": float(ci[0, 0]),
        "ci_hi": float(ci[0, 1]),
        "p": float(fit.pvalues[0]),
        "n_tasks": g,
        "n_rows": df.height,
        "df": dof,
        "n_zero_weight": n_zero,
        "periods": tuple(periods),
    }
