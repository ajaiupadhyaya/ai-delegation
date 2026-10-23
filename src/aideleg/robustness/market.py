"""Market robustness variants of H5/H5b with the null scales recomputed (PAP §3.3, §8.1, D21).

For a variant (return set, exposure vector, dropped industries, scale, window start):

1. Alphas over `confirm_h5.WINDOW` with the bound `power.window_alphas` estimator (daily OLS on
   FF5 + UMD, intercept x 252). Industries named in `drop`, and industries with any missing
   return in the window, are removed; z is not re-standardised.
2. The pre-seal history: the windows x kept-industries alpha matrix on
   `power.historical_windows(first)` (378 windows from 1990-01), returns read with end =
   2022-11-29.
3. `null_scales_for`: the historical slopes on the same fixed z (and control), b-bar = their
   mean, s by `scale`, q = the 0.975 / 0.95 quantiles of |b - b-bar| / s (as `power.own_size`),
   crit_L = max(t_21, q) at Holm levels 0.025 and 0.05.
4. One record per hypothesis: T = (b - b-bar) / s (the D21 null), p = 2(1 - F_21(|T|)),
   interval b +- crit_0.05 * s; the b = 0 statistic goes in `note` as secondary.

These records are reported as robustness; none is a confirmatory decision (PAP §8.1).
AEI data are conversations matched to O*NET tasks.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Literal

import numpy as np
import polars as pl
from scipy import stats as _st

from aideleg import confirm_h5, power
from aideleg.robustness import report, returns
from aideleg.robustness.returns import ReturnSet

Scale = Literal["sd", "nonoverlap_max", "rms"]
SCALES: tuple[str, ...] = ("sd", "nonoverlap_max", "rms")
NULL = "b = bbar"


@dataclass(frozen=True)
class NullScales:
    s: float
    bbar: float
    q_0025: float
    q_005: float
    crit_0025: float
    crit_005: float
    n_windows: int


def _p_t(T: float) -> float:
    return float(2 * _st.t.sf(abs(T), power.T_DF))


def null_scales_for(
    z: np.ndarray, control: np.ndarray | None, alphas_hist: np.ndarray, *, scale: Scale = "sd"
) -> NullScales:
    """s, b-bar, q and the criticals from the historical slopes of `alphas_hist` (windows x
    industries, columns as `z`) on the fixed `z` (and `control`).

    - `sd`: s = sd(b), ddof = 1 (D10; q from `power.own_size` itself).
    - `nonoverlap_max` (R18, §11 C-64): s = the largest sd (ddof = 1) over the 17 offsets of
      `power.non_overlapping`; b-bar stays the all-window mean; q uses the new s.
    - `rms` (R19): s = sqrt(mean((b - b-bar)^2)), the root mean square around the D21 null value.
    """
    if scale not in SCALES:
        raise ValueError(f"unknown scale {scale!r}; one of {SCALES}")
    A = np.asarray(alphas_hist, dtype=float)
    z = np.asarray(z, dtype=float)
    ctl = None if control is None else np.asarray(control, dtype=float)
    b = power.slope_null_distribution(z, [None] * len(A), alphas=A, control=ctl)
    bbar = float(np.mean(b))
    if scale == "sd":
        s = float(np.std(b, ddof=1))
        sz = power.own_size(b, {})
        q25, q5 = sz["q_0.9875"], sz["q_0.975"]
    else:
        if scale == "nonoverlap_max":
            s = max(
                float(np.std(power.non_overlapping(list(b), o), ddof=1))
                for o in range(power.WINDOW_MONTHS)
            )
        else:
            s = float(np.sqrt(np.mean((b - bbar) ** 2)))
        cen = np.abs(b - bbar) / s
        q25, q5 = float(np.quantile(cen, 0.975)), float(np.quantile(cen, 0.95))
    return NullScales(
        s=s,
        bbar=bbar,
        q_0025=q25,
        q_005=q5,
        crit_0025=max(power.t_crit(0.025), q25),
        crit_005=max(power.t_crit(0.05), q5),
        n_windows=len(b),
    )


def history(rs: ReturnSet, names: list[str], *, first: date = power.FIRST_START) -> np.ndarray:
    """The windows x industries alpha matrix (columns as `names`) on the pre-seal windows of
    `power.historical_windows(first)`, returns and factors read with end = 2022-11-29."""
    r = returns.load_return_set(rs, power.END)
    f = returns.load_factors(power.END)
    return power._alpha_matrix(power.historical_windows(first), r, f, list(names))


def _window_alphas(
    rs: ReturnSet, names: list[str], exclude: Callable[[date], bool] | None
) -> np.ndarray:
    end = confirm_h5.WINDOW[1]
    r = returns.load_return_set(rs, end).select("date", *names)
    f = returns.load_factors(end)
    if exclude is not None:
        keep = pl.col("date").map_elements(lambda d: not exclude(d), return_dtype=pl.Boolean)
        r, f = r.filter(keep), f.filter(keep)
    return power.window_alphas(r, f, *confirm_h5.WINDOW).to_numpy().astype(float)


def window_slope(
    z: np.ndarray,
    control: np.ndarray | None,
    rs: ReturnSet,
    names: list[str],
    *,
    exclude: Callable[[date], bool] | None = None,
) -> tuple[float, list[str]]:
    """(b in decimal, the industries dropped for a missing return) over `confirm_h5.WINDOW`;
    dates for which `exclude` is true are left out of the window regression."""
    a = _window_alphas(rs, list(names), exclude)
    ok = ~np.isnan(a)
    z = np.asarray(z, dtype=float)[ok]
    ctl = None if control is None else np.asarray(control, dtype=float)[ok]
    dropped = [n for n, k in zip(names, ok, strict=True) if not k]
    return float(power.ols_weights(z, ctl) @ a[ok]), dropped


def _record(
    row_id: str,
    part: str,
    variant: str,
    hyp: str,
    label: str,
    estimand: str,
    b: float,
    ns: NullScales,
    n: int,
    dropped: list[str],
) -> dict:
    T = (b - ns.bbar) / ns.s
    T0 = b / ns.s
    rec = {
        "row_id": row_id,
        "part": part,
        "variant": variant,
        "applies_to": hyp,
        "label": label,
        "estimand": estimand,
        "unit": report.MARKET_UNIT,
        "estimate": b * 100,
        "scale": ns.s * 100,
        "ci_lo": (b - ns.crit_005 * ns.s) * 100,
        "ci_hi": (b + ns.crit_005 * ns.s) * 100,
        "stat": T,
        "p": _p_t(T),
        "null": NULL,
        "crit_0025": ns.crit_0025,
        "crit_005": ns.crit_005,
        "n": n,
        "n_dropped": len(dropped),
        "dropped": ", ".join(dropped),
        "note": f"secondary b = 0: T = {report.fmt_stat(T0)}, p = {report.fmt_p(_p_t(T0))}",
    }
    report.check_record(rec)
    return rec


def market_variant(
    row_id: str,
    part: str,
    expo: pl.DataFrame,
    *,
    rs: ReturnSet = "ff49_vw",
    drop: tuple[str, ...] = (),
    z_col: str = "z_delegation",
    control_col: str | None = "z_aioe",
    scale: Scale = "sd",
    first: date = power.FIRST_START,
    label: str = "robustness",
) -> list[dict]:
    """Two records in `report.ROBUSTNESS_COLUMNS`: H5 (no control) and H5b (`control_col`).

    `expo` has `industry` (the return set's column names) and the z columns. Industries in
    `drop` and industries with a missing window return are removed from the window and the
    history before the null scales are computed; z is not re-standardised."""
    r_end = returns.load_return_set(rs, confirm_h5.WINDOW[1])  # guarded before anything else
    names = [c for c in r_end.columns if c != "date"]
    if sorted(expo["industry"].to_list()) != sorted(names):
        raise ValueError(f"exposure industries do not match the {rs} return columns")
    unknown = sorted(set(drop) - set(names))
    if unknown:
        raise ValueError(f"drop names industries not in {rs}: {unknown}")
    cols = [z_col] + ([control_col] if control_col else [])
    by = {r["industry"]: r for r in expo.select("industry", *cols).iter_rows(named=True)}
    if any(by[n][c] is None for n in names if n not in drop for c in cols):
        raise ValueError(f"null exposure values in {cols} for a kept industry")

    a = _window_alphas(rs, names, None)
    keep = [n not in drop and not np.isnan(x) for n, x in zip(names, a, strict=True)]
    kept = [n for n, k in zip(names, keep, strict=True) if k]
    dropped = [n for n, k in zip(names, keep, strict=True) if not k]
    ak = a[np.array(keep)]
    z = np.array([by[n][z_col] for n in kept], dtype=float)
    c = None if not control_col else np.array([by[n][control_col] for n in kept], dtype=float)
    A = history(rs, kept, first=first)
    variant = (
        f"returns={rs}; z={z_col}; control={control_col}; scale={scale}; "
        f"first={first}; drop={', '.join(drop) or 'none'}"
    )
    out = []
    for hyp, ctl in (("H5", None), ("H5b", c)):
        if hyp == "H5b" and ctl is None:
            continue
        ns = null_scales_for(z, ctl, A, scale=scale)
        b = float(power.ols_weights(z, ctl) @ ak)
        est = f"slope of annualised FF5+UMD alpha on {z_col}" + (
            f", controlling for {control_col}" if ctl is not None else ""
        )
        out.append(_record(row_id, part, variant, hyp, label, est, b, ns, len(kept), dropped))
    return out
