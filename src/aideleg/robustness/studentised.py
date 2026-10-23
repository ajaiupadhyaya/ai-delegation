"""The R35 studentised statistic (PAP §8.2 R35, P10; moved to Plan 4 by §11 C-29).

For each of the 378 pre-seal windows w (PAP §3.3):

- the daily FF5 + UMD regression of each industry is fitted as `power.window_alphas` fits it
  (excess returns and factors in decimal, intercept x 252);
- Sigma_w is the industries x industries covariance of the daily residuals, denominator T_w - 7;
- c_w = [(X_w'X_w)^-1]_11, the intercept element of the common factor design;
- omega is the OLS weight vector with b = omega'alpha (`power.ols_weights` of [1, z] for H5,
  [1, z, z_aioe] for H5b);
- SE_Sigma,w = 252 * sqrt(c_w * omega' Sigma_w omega);
- kappa = sd_w(b_w) / median_w(SE_Sigma,w), the sd being the same (ddof = 1) as s.

In the confirmatory window SE_Sigma is computed the same way, and
T_stud = (b - b0) / (kappa * SE_Sigma), with b0 the D21 null value and the t_21 criticals.
Reported as robustness only (PAP §8.1).
"""

from datetime import date

import numpy as np
import polars as pl

from aideleg import power
from aideleg.robustness import returns as _returns
from aideleg.robustness.returns import ReturnSet


def se_sigma(
    returns: pl.DataFrame,
    factors: pl.DataFrame,
    start: date,
    end: date,
    omega: np.ndarray,
    names: list[str],
) -> float:
    """SE_Sigma = 252 * sqrt(c * omega' Sigma omega) over [start, end] for the industries
    `names` (ordered as `omega`); inputs in percent, as the French loaders return them.
    Raises if an industry has a missing return in the window."""
    j = (
        returns.select("date", *names)
        .join(factors, on="date", how="inner")
        .filter((pl.col("date") >= start) & (pl.col("date") <= end))
        .sort("date")
    )
    k = len(power.FACTORS) + 1
    if j.height <= k:
        raise ValueError(f"{j.height} days in {start} -> {end}: too few for the FF5+UMD fit")
    if j.select(pl.max_horizontal(pl.col(power.FACTORS + ["rf"]).is_null())).to_series().any():
        raise ValueError(f"missing factor values in {start} -> {end}")
    X = np.column_stack([np.ones(j.height)] + [j[c].to_numpy() / 100 for c in power.FACTORS])
    rf = j["rf"].to_numpy() / 100
    Y = np.column_stack([j[n].to_numpy().astype(float) / 100 - rf for n in names])
    if np.isnan(Y).any():
        bad = [n for n, m in zip(names, np.isnan(Y).any(axis=0), strict=True) if m]
        raise ValueError(f"missing returns in {start} -> {end} for {bad}")
    coef = np.linalg.lstsq(X, Y, rcond=None)[0]
    E = Y - X @ coef
    sigma = E.T @ E / (j.height - k)
    c = float(np.linalg.inv(X.T @ X)[0, 0])
    omega = np.asarray(omega, dtype=float)
    return float(252 * np.sqrt(c * (omega @ sigma @ omega)))


def _ratio(b: np.ndarray, se: np.ndarray) -> float:
    return float(np.std(np.asarray(b, dtype=float), ddof=1) / np.median(np.asarray(se)))


def _history_b_se(
    z: np.ndarray, control: np.ndarray | None, rs: ReturnSet, names: list[str] | None
) -> tuple[np.ndarray, np.ndarray]:
    """(b_w, SE_Sigma,w) over the 378 pre-seal windows, returns read with end = 2022-11-29."""
    r = _returns.load_return_set(rs, power.END)
    f = _returns.load_factors(power.END)
    names = [c for c in r.columns if c != "date"] if names is None else list(names)
    z = np.asarray(z, dtype=float)
    if len(z) != len(names):
        raise ValueError(f"z has {len(z)} values for {len(names)} industries")
    ctl = None if control is None else np.asarray(control, dtype=float)
    windows = power.historical_windows()
    A = power._alpha_matrix(windows, r, f, names)
    b = power.slope_null_distribution(z, [None] * len(A), alphas=A, control=ctl)
    omega = power.ols_weights(z, ctl)
    se = np.array([se_sigma(r, f, s, e, omega, names) for s, e in windows])
    return b, se


def kappa(
    z: np.ndarray,
    control: np.ndarray | None,
    rs: ReturnSet = "ff49_vw",
    *,
    names: list[str] | None = None,
) -> float:
    """kappa = sd(b_w) / median(SE_Sigma,w) over the 378 windows; `z` (and `control`) ordered
    as `names` (default: every column of the return set)."""
    return _ratio(*_history_b_se(z, control, rs, names))


def t_stud(b_hat: float, bbar: float, kappa: float, se_window: float) -> float:
    """T_stud = (b - b0) / (kappa * SE_Sigma,window), with b0 = b-bar (D21)."""
    return (b_hat - bbar) / (kappa * se_window)
