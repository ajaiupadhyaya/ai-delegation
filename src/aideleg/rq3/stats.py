"""Portfolio statistics helpers for the exploratory market tests (Plan 3).

Pure numerical code; nothing here reads data.

- `hac_regression` is OLS with Newey-West (Bartlett kernel) standard errors, no small-sample
  correction, and t-based p-values. The default lag is the Newey-West (1994) rule
  `floor(4 (T/100)^(2/9))` (`nw_lag`).
- `sr`, `sharpe`, `psr`, `dsr` give the Sharpe ratio, the Probabilistic Sharpe Ratio (Bailey
  and Lopez de Prado, 2012) and the Deflated Sharpe Ratio (Bailey and Lopez de Prado, 2014).
- `stationary_indices`, `bootstrap`, `percentile_ci` implement the Politis-Romano (1994)
  stationary bootstrap with a percentile interval.

AEI data are conversations matched to O*NET tasks; nothing here speaks to the labour market.
"""

from collections.abc import Callable

import numpy as np
import statsmodels.api as sm
from scipy import stats as _st

EULER_GAMMA = 0.5772156649


def nw_lag(T: int) -> int:
    """Newey-West (1994) automatic lag: floor(4 * (T / 100) ** (2 / 9))."""
    return int(np.floor(4 * (T / 100) ** (2 / 9)))


def hac_regression(y: np.ndarray, X: np.ndarray | None, lag: int | None = None) -> dict:
    """OLS of y on a constant and X with Newey-West HAC errors; X=None gives the mean.

    Returns coef, se, t, p (constant first), the lag used and T.
    """
    y = np.asarray(y, dtype=float)
    T = len(y)
    L = nw_lag(T) if lag is None else int(lag)
    if X is None:
        design = np.ones((T, 1))
    else:
        design = sm.add_constant(np.asarray(X, dtype=float), has_constant="add")
    res = sm.OLS(y, design).fit(
        cov_type="HAC",
        cov_kwds={"maxlags": L, "kernel": "bartlett", "use_correction": False},
        use_t=True,
    )
    return {
        "coef": np.asarray(res.params),
        "se": np.asarray(res.bse),
        "t": np.asarray(res.tvalues),
        "p": np.asarray(res.pvalues),
        "lag": L,
        "T": T,
    }


def sr(r: np.ndarray) -> float:
    """Per-period Sharpe ratio: mean / sd (ddof = 1)."""
    r = np.asarray(r, dtype=float)
    return float(r.mean() / r.std(ddof=1))


def sharpe(r: np.ndarray, periods: int = 12) -> float:
    """Annualised Sharpe ratio: sr(r) * sqrt(periods)."""
    return sr(r) * float(np.sqrt(periods))


def psr(r: np.ndarray, sr_star: float = 0.0) -> float:
    """Probabilistic Sharpe Ratio: P(true per-period SR > sr_star)."""
    r = np.asarray(r, dtype=float)
    T = len(r)
    s = sr(r)
    g3 = float(_st.skew(r, bias=True))
    g4 = float(_st.kurtosis(r, fisher=False, bias=True))
    var_term = 1 - g3 * s + (g4 - 1) / 4 * s**2
    if not var_term > 0:
        raise ValueError(
            f"psr: non-positive variance term {var_term!r} (skew={g3}, kurt={g4}, sr={s})"
        )
    denom = np.sqrt(var_term)
    return float(_st.norm.cdf((s - sr_star) * np.sqrt(T - 1) / denom))


def dsr(r: np.ndarray, sr_variants: np.ndarray) -> float:
    """Deflated Sharpe Ratio: PSR against the expected maximum SR over N variants."""
    v = np.asarray(sr_variants, dtype=float)
    N = len(v)
    if N < 2:
        raise ValueError("dsr needs at least 2 SR variants")
    g = EULER_GAMMA
    sr0 = np.sqrt(np.var(v, ddof=1)) * (
        (1 - g) * _st.norm.ppf(1 - 1 / N) + g * _st.norm.ppf(1 - 1 / (N * np.e))
    )
    return psr(r, float(sr0))


def stationary_indices(n: int, mean_block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis-Romano indices: restart at a random index w.p. 1/mean_block, else step +1 (wraps)."""
    new = rng.random(n) < 1.0 / mean_block
    new[0] = True
    starts = rng.integers(0, n, size=n)
    pos = np.arange(n)
    where = np.flatnonzero(new)
    seg = np.cumsum(new) - 1
    return (starts[where][seg] + pos - where[seg]) % n


def bootstrap(
    r: np.ndarray,
    stats: dict[str, Callable],
    n_draws: int,
    mean_block: float,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    """One stationary-bootstrap index draw per replicate; every statistic sees the same draw."""
    r = np.asarray(r, dtype=float)
    out = {k: np.empty(n_draws) for k in stats}
    for b in range(n_draws):
        sample = r[stationary_indices(len(r), mean_block, rng)]
        for k, fn in stats.items():
            out[k][b] = fn(sample)
    return out


def percentile_ci(draws: np.ndarray, level: float = 0.95) -> tuple[float, float]:
    """Equal-tailed percentile interval."""
    a = (1 - level) / 2
    lo, hi = np.quantile(np.asarray(draws, dtype=float), [a, 1 - a])
    return float(lo), float(hi)
