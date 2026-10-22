"""The two-way cluster estimator for H1 and H3, exactly as stated at the top of PAP section 4.

WLS with covariance V = V_occ + V_task - V_occ∩task (Cameron, Gelbach & Miller 2011), each
term with the small-sample correction G/(G-1)·(n-1)/(n-k), computed by statsmodels 0.15.0
(`cov_cluster_2groups`). Inference is t with min(G_occ, G_task) - 1 degrees of freedom.

Non-PSD rule (PAP section 4): the tested block V_k is clipped to U·max(Λ, 0)·U' when its
smallest eigenvalue is negative; a tested variance that is then zero is replaced by the larger
of its two one-way cluster variances. Every use is reported on `TwoWayFit`.
"""

from dataclasses import dataclass

import numpy as np
import statsmodels.api as sm
from scipy import stats

from aideleg.rq1.result import Coef

ZERO_VARIANCE_RTOL = 1e-12


@dataclass
class TwoWayFit:
    coefs: dict[str, Coef]  # tested coefficients only
    df_inference: int
    n_obs: int
    g_occ: int
    g_task: int
    psd_clipped: bool
    min_eigenvalue: float  # of the tested block, before clipping
    zero_variance_fallback: list[str]
    se_oneway_occ: dict[str, float]
    se_oneway_task: dict[str, float]
    p_oneway_occ: dict[str, float]  # df = G_occ - 1; reported as R38, used in no decision


def psd_clip(v: np.ndarray) -> tuple[np.ndarray, float]:
    """U·max(Λ, 0)·U' for symmetric v = UΛU', and the smallest eigenvalue Λ."""
    lam, u = np.linalg.eigh(np.asarray(v, dtype=float))
    return (u * np.maximum(lam, 0.0)) @ u.T, float(lam.min())


def resolve_tested_cov(
    v_two: np.ndarray, v_occ: np.ndarray, v_task: np.ndarray, idx: list[int]
) -> tuple[np.ndarray, bool, float, list[int]]:
    """The tested block of v_two after the PAP section 4 non-PSD rule.

    Returns (block, clipped, smallest eigenvalue before clipping, positions in `idx` whose
    variance fell back to the larger one-way cluster variance). Off-diagonals are kept.
    """
    ix = np.asarray(idx, dtype=int)
    block = np.asarray(v_two, dtype=float)[np.ix_(ix, ix)]
    min_eig = float(np.linalg.eigvalsh(block).min())
    clipped = min_eig < 0
    if clipped:
        block, _ = psd_clip(block)
    block = block.copy()
    fallback = []
    for pos, i in enumerate(ix):
        larger = max(float(v_occ[i, i]), float(v_task[i, i]))
        if block[pos, pos] <= ZERO_VARIANCE_RTOL * larger:
            block[pos, pos] = larger
            fallback.append(pos)
        if not block[pos, pos] > 0:
            raise ValueError(f"tested coefficient {i}: zero variance in all three covariances")
    return block, clipped, min_eig, fallback


def _t_coef(name: str, estimate: float, var: float, df: int) -> Coef:
    se = float(np.sqrt(var))
    half = float(stats.t.ppf(0.975, df)) * se
    p = float(2 * stats.t.sf(abs(estimate / se), df))
    return Coef(name, float(estimate), se, estimate - half, estimate + half, p, df)


def twoway_wls(y, X, w, occ_id, task_id, *, names: list[str], tested: list[str]) -> TwoWayFit:
    """WLS of y on X with two-way (occupation, task) clustered inference (PAP section 4).

    Callers pass complete arrays: no row is ever dropped here, and a missing or non-finite
    value is an error.
    """
    y, X, w = np.asarray(y, float), np.asarray(X, float), np.asarray(w, float)
    occ_id, task_id = np.asarray(occ_id), np.asarray(task_id)
    if X.ndim != 2 or X.shape[1] != len(names) or len(set(names)) != len(names):
        raise ValueError("X must be 2-D with one column per unique name")
    n = X.shape[0]
    if any(a.shape != (n,) for a in (y, w, occ_id, task_id)):
        raise ValueError("y, w, occ_id and task_id must be 1-D with one value per row of X")
    if not (np.isfinite(y).all() and np.isfinite(X).all() and np.isfinite(w).all()):
        raise ValueError("missing or non-finite values: callers must pass complete arrays")
    if (w <= 0).any():
        raise ValueError("weights must be positive")
    if not tested or any(t not in names for t in tested):
        raise ValueError(f"tested {tested} must be a non-empty subset of names")

    # PAP section 4, verbatim.
    fit = sm.WLS(y, X, weights=w).fit(
        cov_type="cluster",
        cov_kwds={"groups": np.column_stack([occ_id, task_id]), "use_correction": True},
        use_t=True)

    g_occ, g_task = len(np.unique(occ_id)), len(np.unique(task_id))
    df = int(fit.df_resid_inference)
    if df != min(g_occ, g_task) - 1:
        raise AssertionError(f"df_resid_inference {df} != min(G) - 1 for G = {g_occ, g_task}")

    def one_way(groups):
        return fit.get_robustcov_results(
            cov_type="cluster", groups=groups, use_correction=True, use_t=True)

    v_occ = np.asarray(one_way(occ_id).cov_params())
    v_task = np.asarray(one_way(task_id).cov_params())

    idx = [names.index(t) for t in tested]
    block, clipped, min_eig, fallback = resolve_tested_cov(
        np.asarray(fit.cov_params()), v_occ, v_task, idx)

    params = np.asarray(fit.params)
    coefs, se_occ, se_task, p_occ = {}, {}, {}, {}
    for pos, (name, i) in enumerate(zip(tested, idx, strict=True)):
        coefs[name] = _t_coef(name, params[i], block[pos, pos], df)
        oneway_occ = _t_coef(name, params[i], v_occ[i, i], g_occ - 1)
        se_occ[name], p_occ[name] = oneway_occ.se, oneway_occ.p
        se_task[name] = float(np.sqrt(v_task[i, i]))

    return TwoWayFit(
        coefs=coefs, df_inference=df, n_obs=int(fit.nobs), g_occ=g_occ, g_task=g_task,
        psd_clipped=clipped, min_eigenvalue=min_eig,
        zero_variance_fallback=[tested[pos] for pos in fallback],
        se_oneway_occ=se_occ, se_oneway_task=se_task, p_oneway_occ=p_occ)
