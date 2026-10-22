"""H1 and H3 estimators (PAP §4.1, §4.3, D17, P13).

AEI data are conversations matched to O*NET tasks. A row is one (task, occupation, IWA)
allocation of those conversations; H1 and H3 describe how tasks differ, weighted by the
occupations they are allocated to. They do not compare workers.

Rules
- **Variable-level drops** apply only to the estimator's own variables (outcome, then
  predictors or indicator, then covariates), each row counted once under its first reason:
  `missing_<col>` (null or NaN). For `log_wage` the reason follows `wage_status`:
  `no_oews_code`, `wage_suppressed` (status `suppressed`), `no_wage_row`; otherwise
  `missing_log_wage`. Shares are in percent of `tr.total_weight`, after `tr.structural_drops`.
  Weights are not renormalised.
  - Interpretation fixed now (PAP §4.1 "H3 applies the same rule to its own variables"): H3
    with no covariates requires no OEWS code, wage or education.
- **Design.** Regressors first, then one dummy per IWA family present in the sample, with no
  constant. The family dummies are the IWA fixed effects. Inference is `twoway_wls` (PAP §4).
- **H1.** p_family = max(p_educ, p_wage), the intersection-union p-value (D17). The tested
  block of the non-PSD rule is [β_e, β_w].
- **H3.** p_family = p of the indicator. The tested block of the non-PSD rule is γ alone
  (PAP §4); covariates (R31) are reported from a second call on the same design whose tested
  block is the covariates, so they never change γ's inference.
- **P13.** `attenuation_factor` is the between-task share of the regressor's effective
  (Frisch-Waugh-Lovell) variation: the wage (H1) or the indicator (H3) residualised by WLS on
  the IWA FE and on the estimator's other regressors (education in H1; the covariates in H3
  with covariates). It is reported beside β_w and γ.
"""

import math

import numpy as np
import polars as pl

from aideleg.rq1.result import HypothesisResult
from aideleg.rq1.rows import TaskRows
from aideleg.rq1.twoway import TwoWayFit, twoway_wls

_WAGE_REASON = {"no_oews_code": "no_oews_code", "suppressed": "wage_suppressed",
                "no_wage_row": "no_wage_row"}
_FIT_FIELDS = ("df_inference", "n_obs", "g_occ", "g_task", "psd_clipped", "min_eigenvalue",
               "zero_variance_fallback", "se_oneway_occ", "se_oneway_task", "p_oneway_occ")


def _group_mean(x: np.ndarray, w: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """The w-weighted mean of x within each label, returned per row."""
    sw = np.bincount(labels, weights=w)
    return (np.bincount(labels, weights=w * x) / sw)[labels]


def attenuation_factor(x: np.ndarray, w: np.ndarray, family: np.ndarray,
                       task: np.ndarray, controls: np.ndarray | None = None) -> float:
    """Σ w·r̄² / Σ w·r², the between-task share of the regressor's effective variation (P13).

    r is the Frisch-Waugh-Lovell residual of x: x residualised by WLS (weights w) on the
    family fixed effects and on `controls` (the estimator's other regressors, n x k; none by
    default, when r is x minus its w-weighted family mean). r̄ is the w-weighted mean of r
    within (task, family). β of x is identified from r alone, so this is the share of its
    identifying variation that lies between tasks."""
    x, w = np.asarray(x, float), np.asarray(w, float)
    fam = np.unique(np.asarray(family), return_inverse=True)[1].ravel()
    tsk = np.unique(np.asarray(task), return_inverse=True)[1].ravel()
    cell = np.unique(np.column_stack([tsk, fam]), axis=0, return_inverse=True)[1].ravel()
    r = x - _group_mean(x, w, fam)
    if controls is not None and np.size(controls):
        c = np.asarray(controls, float).reshape(len(x), -1)
        c = c - np.column_stack([_group_mean(c[:, j], w, fam) for j in range(c.shape[1])])
        sw = np.sqrt(w)
        coef = np.linalg.lstsq(c * sw[:, None], r * sw, rcond=None)[0]
        r = r - c @ coef
    r_bar = _group_mean(r, w, cell)
    return float(np.sum(w * r_bar**2) / np.sum(w * r**2))


def _drop_reason(rows: pl.DataFrame, col: str) -> pl.Expr:
    """Per-row drop reason for one variable, null when the value is present."""
    missing = pl.col(col).is_null()
    if rows.schema[col].is_float():
        missing = missing | pl.col(col).is_nan()
    if col == "log_wage":
        reason = pl.col("wage_status").replace_strict(_WAGE_REASON, default="missing_log_wage")
    else:
        reason = pl.lit(f"missing_{col}")
    return pl.when(missing).then(reason)


def _apply_drops(tr: TaskRows, cols: list[str]) -> tuple[pl.DataFrame, dict[str, float]]:
    """Rows complete in `cols`, and the structural plus variable drop shares (% of total)."""
    rows = tr.rows.with_columns(_reason=pl.lit(None, pl.String))
    keys: list[str] = []
    for c in cols:
        keys += ([*_WAGE_REASON.values(), "missing_log_wage"] if c == "log_wage"
                 else [f"missing_{c}"])
        rows = rows.with_columns(_reason=pl.coalesce("_reason", _drop_reason(rows, c)))
    by = dict(rows.group_by("_reason").agg(pl.col("weight").sum()).drop_nulls().iter_rows())
    drops = dict(tr.structural_drops)
    for k in keys:
        if k != "missing_log_wage" or k in by:
            drops[k] = float(by.get(k, 0.0)) / tr.total_weight * 100
    return rows.filter(pl.col("_reason").is_null()).drop("_reason"), drops


def _design(rows: pl.DataFrame, regressors: list[str]) -> tuple[np.ndarray, list[str]]:
    families = sorted(set(rows["family"]))
    fam = rows["family"].to_numpy()
    dummies = np.column_stack([(fam == f).astype(float) for f in families])
    X = np.column_stack([rows.select(regressors).to_numpy().astype(float), dummies])
    return X, [*regressors, *(f"family:{f}" for f in families)]


def _fit(rows: pl.DataFrame, outcome: str, regressors: list[str],
         tested: list[str]) -> TwoWayFit:
    X, names = _design(rows, regressors)
    return twoway_wls(rows[outcome].to_numpy(), X, rows["weight"].to_numpy(),
                      rows["occ_code"].to_numpy(), rows["task_code"].to_numpy(),
                      names=names, tested=tested)


def _psd_note(fit: TwoWayFit, tested: list[str]) -> list[str]:
    if not (fit.psd_clipped or fit.zero_variance_fallback):
        return []
    fallback = (f"SE of {', '.join(fit.zero_variance_fallback)} set to the larger one-way "
                "cluster SE" if fit.zero_variance_fallback else "no variance fell back to a "
                "one-way cluster SE")
    return [f"non-PSD rule applied to [{', '.join(tested)}]: smallest eigenvalue "
            f"{fit.min_eigenvalue:.6g}; {fallback}"]


def _sample(rows: pl.DataFrame, fit: TwoWayFit) -> dict[str, int]:
    n_occ = rows["occ_code"].n_unique()
    if n_occ != rows["soc6"].n_unique():
        raise AssertionError("occ_code and soc6 disagree on the number of occupations")
    return {"n_rows": rows.height, "n_tasks": rows["task_code"].n_unique(),
            "n_occ": n_occ, "n_family": rows["family"].n_unique(),
            "g_occ": fit.g_occ, "g_task": fit.g_task, "df_inference": fit.df_inference}


def _attenuation(rows: pl.DataFrame, col: str, regressors: list[str]) -> float:
    """P13 factor of `col`, residualised on the IWA FE and the other regressors (FWL)."""
    others = [c for c in regressors if c != col]
    controls = rows.select(others).to_numpy().astype(float) if others else None
    return attenuation_factor(rows[col].to_numpy().astype(float), rows["weight"].to_numpy(),
                              rows["family"].to_numpy(), rows["task_code"].to_numpy(),
                              controls)


def _p_intersection_union(ps: list[float]) -> float:
    """max of the p-values (D17); NaN if any is NaN, so a NaN is never dropped by max."""
    return math.nan if any(math.isnan(p) for p in ps) else max(ps)


def estimate_h1(tr: TaskRows, outcome: str = "automation_pct",
                predictors: tuple[str, str] = ("human_education_years_mean", "log_wage")
                ) -> HypothesisResult:
    """H1: outcome = β_e·education + β_w·log wage + IWA FE (PAP §4.1); p = max (D17)."""
    tested = list(predictors)
    rows, drops = _apply_drops(tr, [outcome, *tested])
    fit = _fit(rows, outcome, tested, tested)
    diagnostics = {k: getattr(fit, k) for k in _FIT_FIELDS}
    diagnostics["attenuation_log_wage"] = _attenuation(rows, predictors[1], tested)
    diagnostics["tested"] = list(tested)
    return HypothesisResult(
        hypothesis="H1", outcome=outcome, coefs=fit.coefs,
        p_family=_p_intersection_union([fit.coefs[p].p for p in tested]),
        sample=_sample(rows, fit),
        drops=drops, diagnostics=diagnostics, notes=_psd_note(fit, tested))


def estimate_h3(tr: TaskRows, outcome: str = "validation_pct", indicator: str = "error_cost",
                covariates: tuple[str, ...] = ()) -> HypothesisResult:
    """H3: outcome = γ·indicator (+ covariates, R31) + IWA FE (PAP §4.3); p = p_γ."""
    regressors = [indicator, *covariates]
    rows, drops = _apply_drops(tr, [outcome, *regressors])
    fit = _fit(rows, outcome, regressors, [indicator])
    coefs, notes = dict(fit.coefs), _psd_note(fit, [indicator])
    diagnostics = {k: getattr(fit, k) for k in _FIT_FIELDS}
    diagnostics["tested"] = [indicator]
    if covariates:
        cov_fit = _fit(rows, outcome, regressors, list(covariates))
        coefs.update(cov_fit.coefs)
        notes += _psd_note(cov_fit, list(covariates))
        diagnostics["covariates_psd"] = {
            "psd_clipped": cov_fit.psd_clipped, "min_eigenvalue": cov_fit.min_eigenvalue,
            "zero_variance_fallback": cov_fit.zero_variance_fallback}
        for k in ("se_oneway_occ", "se_oneway_task", "p_oneway_occ"):
            diagnostics[k] = {**getattr(fit, k), **getattr(cov_fit, k)}
    diagnostics[f"attenuation_{indicator}"] = _attenuation(rows, indicator, regressors)
    return HypothesisResult(
        hypothesis="H3", outcome=outcome, coefs=coefs, p_family=fit.coefs[indicator].p,
        sample=_sample(rows, fit), drops=drops, diagnostics=diagnostics, notes=notes)
