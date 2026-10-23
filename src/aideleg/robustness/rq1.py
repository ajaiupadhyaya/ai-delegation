"""H1/H3 robustness pieces (Plan 4 Task 11): the records of a Plan 2 `HypothesisResult`, the
H3 validation bounds (R10) and the Consequence-of-Error column (R27).

Everything else (rows, estimators, inference) is Plan 2's, through `upstream`. The only new
RQ1 constructions are `validation_bounds` (PAP §11 C-57) and `with_coe` (C-58).

AEI data are conversations matched to O*NET tasks. H1 and H3 describe how tasks differ,
weighted by the occupations they are allocated to; they do not compare workers.
"""

import dataclasses
import math

import polars as pl
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

__all__ = [
    "AUTONOMY_UNIT",
    "R23_DISAGREE",
    "RQ1_UNIT",
    "consequence_of_error",
    "r23_disagrees",
    "rq1_records",
    "validation_bounds",
    "with_coe",
    "with_validation_bounds",
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
