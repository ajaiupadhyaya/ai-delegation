"""The PAP section 4 two-way cluster estimator, checked on synthetic data only."""

import numpy as np
import pytest
from scipy import stats

from aideleg.config import SEED
from aideleg.rq1 import twoway
from aideleg.rq1.result import Coef

NAMES = ["const", "x1", "x2"]
TESTED = ["x1", "x2"]


def _synthetic(n=200, g_occ=15, g_task=20, seed=SEED):
    rng = np.random.default_rng(seed)
    occ = rng.integers(0, g_occ, n)
    task = rng.integers(0, g_task, n)
    occ[:g_occ] = np.arange(g_occ)  # every cluster appears
    task[:g_task] = np.arange(g_task)
    X = np.column_stack([np.ones(n), rng.normal(size=n), rng.normal(size=n)])
    u = rng.normal(size=g_occ)[occ] + rng.normal(size=g_task)[task] + rng.normal(size=n)
    y = X @ np.array([1.0, -0.5, 0.3]) + u
    w = rng.uniform(0.5, 3.0, n)
    return y, X, w, occ, task


def _cgm_manual(y, X, w, occ, task):
    """Independent CGM (2011) two-way CRV1, written from the sandwich formulas."""
    n, k = X.shape
    sw = np.sqrt(w)
    wexog, wy = X * sw[:, None], y * sw
    bread = np.linalg.inv(wexog.T @ wexog)  # (X'WX)^-1
    beta = bread @ wexog.T @ wy
    scores = wexog * (wy - wexog @ beta)[:, None]  # wexog * wresid

    def one_way(groups):
        labels = np.unique(groups, axis=0, return_inverse=True)[1].ravel()
        g = labels.max() + 1
        sums = np.zeros((g, k))
        np.add.at(sums, labels, scores)
        c = g / (g - 1) * (n - 1) / (n - k)
        return c * bread @ (sums.T @ sums) @ bread

    v_occ, v_task = one_way(occ), one_way(task)
    v_both = one_way(np.column_stack([occ, task]))
    return beta, v_occ + v_task - v_both, v_occ, v_task


def test_matches_manual_cgm():
    y, X, w, occ, task = _synthetic()
    fit = twoway.twoway_wls(y, X, w, occ, task, names=NAMES, tested=TESTED)
    beta, v, v_occ, v_task = _cgm_manual(y, X, w, occ, task)
    assert not fit.psd_clipped and fit.zero_variance_fallback == []
    for i, name in enumerate(NAMES):
        if name not in TESTED:
            assert name not in fit.coefs
            continue
        c = fit.coefs[name]
        assert isinstance(c, Coef) and c.name == name
        np.testing.assert_allclose(c.estimate, beta[i], rtol=1e-10)
        np.testing.assert_allclose(c.se, np.sqrt(v[i, i]), rtol=1e-10)
        np.testing.assert_allclose(fit.se_oneway_occ[name], np.sqrt(v_occ[i, i]), rtol=1e-10)
        np.testing.assert_allclose(fit.se_oneway_task[name], np.sqrt(v_task[i, i]), rtol=1e-10)
        t_occ = beta[i] / np.sqrt(v_occ[i, i])
        np.testing.assert_allclose(fit.p_oneway_occ[name], 2 * stats.t.sf(abs(t_occ), 14),
                                   rtol=1e-10)


def test_df_is_min_clusters_minus_one():
    y, X, w, occ, task = _synthetic()
    fit = twoway.twoway_wls(y, X, w, occ, task, names=NAMES, tested=TESTED)
    assert (fit.g_occ, fit.g_task, fit.n_obs) == (15, 20, 200)
    assert fit.df_inference == 14
    assert all(c.df == 14 for c in fit.coefs.values())


def test_psd_clip_known_matrix():
    clipped, min_eig = twoway.psd_clip(np.array([[1.0, 2.0], [2.0, 1.0]]))
    np.testing.assert_allclose(clipped, [[1.5, 1.5], [1.5, 1.5]], atol=1e-14)
    assert min_eig == pytest.approx(-1.0)


def test_psd_clip_leaves_psd_matrix_alone():
    v = np.array([[2.0, 0.5], [0.5, 1.0]])
    clipped, min_eig = twoway.psd_clip(v)
    np.testing.assert_allclose(clipped, v, rtol=1e-12)
    assert min_eig > 0


def test_resolve_tested_cov_clips_and_falls_back():
    block, clipped, min_eig, fallback = twoway.resolve_tested_cov(
        np.array([[-0.5]]), np.array([[0.04]]), np.array([[0.09]]), [0])
    assert block[0, 0] == pytest.approx(0.09) and np.sqrt(block[0, 0]) == pytest.approx(0.3)
    assert clipped is True and min_eig == pytest.approx(-0.5) and fallback == [0]


def test_resolve_tested_cov_takes_block_and_keeps_off_diagonals():
    v_two = np.array([[4.0, 0.0, 1.0], [0.0, 9.0, 0.0], [1.0, 0.0, 0.0]])
    v_occ = np.diag([1.0, 1.0, 0.25])
    v_task = np.diag([1.0, 1.0, 0.36])
    # Block [0, 2] = [[4, 1], [1, 0]] has a negative eigenvalue: it is clipped, no zero variance.
    block, clipped, min_eig, fallback = twoway.resolve_tested_cov(v_two, v_occ, v_task, [0, 2])
    assert clipped and min_eig < 0 and fallback == []
    expect, _ = twoway.psd_clip(np.array([[4.0, 1.0], [1.0, 0.0]]))
    np.testing.assert_allclose(block, expect, rtol=1e-12)
    # Block [1, 2] = diag(9, 0): PSD, not clipped, but variance 0 falls back to max one-way.
    block, clipped, min_eig, fallback = twoway.resolve_tested_cov(v_two, v_occ, v_task, [1, 2])
    assert not clipped and min_eig == pytest.approx(0.0) and fallback == [1]
    np.testing.assert_allclose(block, [[9.0, 0.0], [0.0, 0.36]])


def test_fallback_reported_in_fit():
    # 2 occupations x 2 tasks, one row per cell, intercept only. The residuals are the cell
    # score sums s = [[1.2, -1], [-1, 0.8]], which cancel along both cluster dimensions:
    # V_occ = V_task = 2 * 0.08 / 16 = 0.01, V_cell = 4/3 * 4.08 / 16 = 0.34, so V_two < 0.
    occ, task = np.array([0, 0, 1, 1]), np.array([0, 1, 0, 1])
    y = np.array([1.2, -1.0, -1.0, 0.8]) + 5.0
    fit = twoway.twoway_wls(y, np.ones((4, 1)), np.ones(4), occ, task,
                            names=["const"], tested=["const"])
    assert fit.psd_clipped and fit.min_eigenvalue == pytest.approx(0.02 - 0.34)
    assert fit.zero_variance_fallback == ["const"]
    c = fit.coefs["const"]
    assert c.estimate == pytest.approx(5.0)
    assert c.se == pytest.approx(0.1) and c.se == pytest.approx(fit.se_oneway_occ["const"])
    assert np.isfinite(c.p) and c.df == 1


def test_p_and_ci_use_df_inference():
    y, X, w, occ, task = _synthetic()
    fit = twoway.twoway_wls(y, X, w, occ, task, names=NAMES, tested=TESTED)
    for c in fit.coefs.values():
        assert c.p == pytest.approx(2 * stats.t.sf(abs(c.estimate / c.se), fit.df_inference),
                                    rel=1e-12)
        half = stats.t.ppf(0.975, fit.df_inference) * c.se
        assert c.ci_high - c.estimate == pytest.approx(half, rel=1e-12)
        assert c.estimate - c.ci_low == pytest.approx(half, rel=1e-12)


def test_never_drops_rows():
    y, X, w, occ, task = _synthetic()
    y = y.copy()
    y[3] = np.nan
    with pytest.raises(ValueError):
        twoway.twoway_wls(y, X, w, occ, task, names=NAMES, tested=TESTED)
