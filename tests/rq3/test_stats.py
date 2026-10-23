"""Portfolio statistics helpers: Newey-West HAC, Sharpe/PSR/DSR, stationary bootstrap.

Synthetic data only; no market data are read.
"""

import math

import numpy as np
import pytest
import statsmodels.api as sm

from aideleg.config import SEED
from aideleg.rq3 import stats


def _series() -> np.ndarray:
    rng = np.random.default_rng(7)
    return rng.normal(0.01, 0.04, 24)


def test_nw_lag_rule():
    assert [stats.nw_lag(t) for t in (17, 45, 100, 250)] == [2, 3, 4, 4]


def test_hac_lag0_equals_hc0():
    rng = np.random.default_rng(1)
    X = rng.normal(size=(60, 2))
    y = 0.3 + X @ np.array([0.5, -0.2]) + rng.normal(size=60)
    out = stats.hac_regression(y, X, lag=0)
    ref = sm.OLS(y, sm.add_constant(X)).fit(cov_type="HC0")
    assert np.allclose(out["se"], ref.bse, atol=1e-10, rtol=0)
    assert np.allclose(out["coef"], ref.params, atol=1e-10, rtol=0)
    assert out["lag"] == 0 and out["T"] == 60


def test_hac_mean_only():
    y = _series()
    out = stats.hac_regression(y, None)
    assert len(out["coef"]) == 1
    assert out["coef"][0] == pytest.approx(y.mean())
    assert out["lag"] == stats.nw_lag(24)


def test_psr_is_half_at_its_own_sr():
    r = _series()
    assert stats.psr(r, stats.sr(r)) == pytest.approx(0.5, abs=1e-15)


def test_psr_matches_formula():
    r = _series()
    T = len(r)
    s = r.mean() / r.std(ddof=1)
    m = r - r.mean()
    g3 = (m**3).mean() / (m**2).mean() ** 1.5
    g4 = (m**4).mean() / (m**2).mean() ** 2
    z = (s - 0.1) * math.sqrt(T - 1) / math.sqrt(1 - g3 * s + (g4 - 1) / 4 * s**2)
    expected = 0.5 * (1 + math.erf(z / math.sqrt(2)))
    assert stats.psr(r, 0.1) == pytest.approx(expected, abs=1e-12, rel=0)
    assert stats.sharpe(r, 12) == pytest.approx(s * math.sqrt(12))


def test_dsr_below_psr_zero():
    r = _series()
    assert stats.dsr(r, np.array([0.1, 0.2, 0.3])) < stats.psr(r, 0.0)
    with pytest.raises(ValueError):
        stats.dsr(r, np.array([0.1]))


def test_stationary_bootstrap_mean_block_length():
    rng = np.random.default_rng(SEED)
    n, runs, steps = 1000, 0, 0
    for _ in range(200):
        idx = stats.stationary_indices(n, 3.0, rng)
        assert len(idx) == n and idx.min() >= 0 and idx.max() < n
        breaks = np.count_nonzero(idx[1:] != (idx[:-1] + 1) % n)
        runs += breaks + 1
        steps += n
    lens = steps / runs
    assert abs(lens - 3.0) < 0.15


def test_bootstrap_reproducible():
    r = _series()
    fns = {"mean": np.mean, "sharpe": stats.sharpe}
    a = stats.bootstrap(r, fns, 50, 3.0, np.random.default_rng(SEED))
    b = stats.bootstrap(r, fns, 50, 3.0, np.random.default_rng(SEED))
    assert set(a) == {"mean", "sharpe"}
    for k in a:
        assert a[k].shape == (50,)
        assert np.array_equal(a[k], b[k])


def test_percentile_ci():
    lo, hi = stats.percentile_ci(np.arange(101.0), 0.90)
    assert (lo, hi) == (pytest.approx(5.0), pytest.approx(95.0))
