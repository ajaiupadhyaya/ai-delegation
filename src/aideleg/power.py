"""Pre-seal power analysis for the confirmatory market hypotheses H5 and H5b (spec §5.4.1).

H5 is the cross-sectional slope of the 49 FF49 industries' FF5+UMD alphas (daily,
value-weighted, over the 17-month Design B window) on standardised Design B delegation
exposure. H5b is the same slope with Felten-Raj-Seamans AIOE added as a control.

Method. The Design B exposure vector `z_delegation` (and `z_aioe` for H5b) is held FIXED and
the alphas come from historical 17-month windows that all end before the market seal
(2022-11-30). With no true relation between this year's exposure and decades-old alphas, the
spread of those slopes across windows is the sampling noise of the slope: its sd gives the
minimum detectable effect, MDE = (z_{1-alpha/2} + z_power) * sd. alpha = 0.025 is Holm's first
step over {H5, H5b} (0.05 / 2), power = 0.80.

Pre-freeze additions (referee items C1-C5, Task 15b): t_21 criticals and MDEs (nu = 21 fixed,
about 22 independent windows); the in-sample size of the D10 rule on the historical windows
(centred and uncentred, normal and t_21), with kurtosis and empirical centred quantiles; the
1963 start; leverage and OLS weights per industry; the null scales of R12 and R13; and a
"Frozen values" list that `aideleg.confirm_h5` hard-codes.

Integrity. Returns are read only through the French loaders with end = 2022-11-29, and every
row is re-checked against the seal. The historical slopes themselves are not a finding: only
their dispersion, rejection rates, quantiles, kurtosis and the window counts are reported,
plus their mean b-bar, which the referee ruled is frozen (pre-seal, fixed vector) for the
interpretive check. Its sign is not interpreted anywhere.
AEI data are conversations matched to O*NET tasks; nothing here says anything about job risk
or displacement in the labour market.

Run: `uv run python -m aideleg.power` -> docs/pap/power.md (the generated block is rewritten;
text outside it is kept).
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from statistics import NormalDist

import numpy as np
import polars as pl
from scipy import stats as _st

from aideleg.config import DERIVED, ROOT, SEAL_DATE, SEED
from aideleg.market.french import load_factors, load_industry_returns

END = date(2022, 11, 29)  # last pre-seal day; never request anything later
FIRST_START = date(1990, 1, 1)
WINDOW_MONTHS = 17  # Design B: 2025-04-01 -> 2026-08-31
ALPHA = 0.025
POWER = 0.80
FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
OUT = ROOT / "docs/pap/power.md"
BEGIN, FINISH = "<!-- BEGIN GENERATED: python -m aideleg.power -->", "<!-- END GENERATED -->"
N_PERM = 10_000  # spec §5.4: >= 10,000 draws
PLAUSIBILITY_PP = 5.0  # plan-file rule (Task 15), reported for reference only
T_DF = 21  # ~22 independent 17-month windows in 1990-2022 -> nu = 21 (referee C1, fixed)
HOLM_LEVELS = (0.025, 0.05)  # Holm's two steps over {H5, H5b}
SOFTW = "Softw"
FROZEN_HEAD = "## Frozen values"


def _add_months(d: date, k: int) -> date:
    m = d.month - 1 + k
    return date(d.year + m // 12, m % 12 + 1, 1)


def historical_windows(first: date = FIRST_START, last_end: date = END,
                       months: int = WINDOW_MONTHS) -> list[tuple[date, date]]:
    """17-month windows (first of month -> last day of the 17th month), stepped monthly from
    `first`, keeping every window whose end is <= `last_end`."""
    out = []
    start = first
    while True:
        end = _add_months(start, months) - timedelta(days=1)
        if end > last_end:
            return out
        out.append((start, end))
        start = _add_months(start, 1)


def non_overlapping(windows: list[tuple[date, date]], offset: int = 0
                    ) -> list[tuple[date, date]]:
    """Every WINDOW_MONTHS-th window starting at index `offset` (back-to-back, disjoint)."""
    return windows[offset::WINDOW_MONTHS]


def _window_alpha_array(returns: pl.DataFrame, factors: pl.DataFrame, start: date, end: date
                        ) -> np.ndarray:
    """Annualised FF5+UMD alphas (decimal) for every industry column; NaN where any return in
    the window is missing."""
    j = returns.join(factors, on="date", how="inner").filter(
        (pl.col("date") >= start) & (pl.col("date") <= end)).sort("date")
    names = [c for c in returns.columns if c != "date"]
    if j.height <= len(FACTORS) + 1:
        return np.full(len(names), np.nan)
    if j.select(pl.max_horizontal(pl.col(FACTORS + ["rf"]).is_null())).to_series().any():
        raise ValueError(f"missing factor values in {start} -> {end}")
    X = np.column_stack([np.ones(j.height)] + [j[c].to_numpy() / 100 for c in FACTORS])
    rf = j["rf"].to_numpy() / 100
    Y = np.column_stack([j[n].to_numpy().astype(float) / 100 - rf for n in names])
    alphas = np.full(len(names), np.nan)
    ok = ~np.isnan(Y).any(axis=0)
    if ok.any():
        coef = np.linalg.lstsq(X, Y[:, ok], rcond=None)[0]
        alphas[ok] = coef[0] * 252
    return alphas


def window_alphas(returns: pl.DataFrame, factors: pl.DataFrame, start: date, end: date
                  ) -> pl.Series:
    """49 annualised FF5+UMD alphas (decimal per year) from daily OLS of industry excess
    returns over [start, end]. Inputs are in percent, as the French loaders return them.
    An industry with any missing return in the window gets null."""
    a = _window_alpha_array(returns, factors, start, end)
    return pl.Series("alpha", [None if np.isnan(x) else float(x) for x in a], dtype=pl.Float64)


def _cross_section(alphas: np.ndarray, z: np.ndarray, control: np.ndarray | None
                   ) -> tuple[float, float, int]:
    """OLS of alphas on [1, z(, control)] over industries with an alpha: (coef on z, its
    conventional SE, n)."""
    ok = ~np.isnan(alphas)
    cols = [np.ones(ok.sum()), z[ok]] + ([control[ok]] if control is not None else [])
    X = np.column_stack(cols)
    y = alphas[ok]
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = len(y) - X.shape[1]
    s2 = resid @ resid / dof
    se = float(np.sqrt(s2 * np.linalg.inv(X.T @ X)[1, 1]))
    return float(coef[1]), se, int(ok.sum())


def _load_returns() -> tuple[pl.DataFrame, pl.DataFrame]:
    returns = load_industry_returns("D", "VW", END)
    factors = load_factors("D", END)
    for name, df in (("returns", returns), ("factors", factors)):
        if df.height and df["date"].max() >= SEAL_DATE:
            raise RuntimeError(f"{name} contain dates on or after {SEAL_DATE}")
    return returns, factors


def _alpha_matrix(windows, returns, factors, names: list[str]) -> np.ndarray:
    """windows x industries matrix of annualised alphas, columns ordered as `names`."""
    returns = returns.select("date", *names)
    return np.vstack([_window_alpha_array(returns, factors, s, e) for s, e in windows])


def slope_null_distribution(z: np.ndarray, windows: list[tuple[date, date]], *,
                            returns: pl.DataFrame | None = None,
                            factors: pl.DataFrame | None = None,
                            control: np.ndarray | None = None,
                            alphas: np.ndarray | None = None) -> np.ndarray:
    """One cross-sectional OLS slope of window alphas on the FIXED exposure vector `z` per
    historical window (coefficient on `z`; with `control`, the regression is on [z, control]).
    `z` is ordered as the industry columns of `returns`. Defaults load pre-seal French data.
    `alphas` (windows x industries, as `_alpha_matrix` builds it) skips re-estimation."""
    z = np.asarray(z, dtype=float)
    if alphas is None:
        if returns is None or factors is None:
            returns, factors = _load_returns()
        names = [c for c in returns.columns if c != "date"]
        if len(z) != len(names):
            raise ValueError(f"z has {len(z)} values for {len(names)} industries")
        alphas = _alpha_matrix(windows, returns, factors, names)
    if alphas.shape != (len(windows), len(z)):
        raise ValueError(f"alphas are {alphas.shape}, expected {(len(windows), len(z))}")
    if control is not None:
        control = np.asarray(control, dtype=float)
        if len(control) != len(z):
            raise ValueError(f"control has {len(control)} values, z has {len(z)}")
    return np.array([_cross_section(a, z, control)[0] for a in alphas])


def ri_pvalues(alphas: np.ndarray, z: np.ndarray, control: np.ndarray | None = None,
               n_perm: int = 10_000, rng: np.random.Generator | None = None,
               scheme: str = "exposure") -> np.ndarray:
    """Per window (row of `alphas`), the two-sided randomisation-inference p-value of the
    coefficient on `z`, p = (1 + #{|b_perm| >= |b_obs|}) / (n_perm + 1), over the industries
    with an alpha. Only p-values are returned.

    - `scheme="exposure"` (the spec's wording, "shuffle exposure across industries"): `z` is
      permuted, the control (if any) stays in place.
    - `scheme="freedman_lane"`: alphas are regressed on [1(, control)] and the residuals are
      permuted (Freedman & Lane 1983). Without a control the two schemes coincide in
      distribution; with a control correlated with `z`, permuting `z` alone breaks that
      correlation and is oversized even when industries are exchangeable."""
    if scheme not in ("exposure", "freedman_lane"):
        raise ValueError(f"unknown scheme {scheme!r}")
    rng = np.random.default_rng(SEED) if rng is None else rng
    z = np.asarray(z, dtype=float)
    out = np.empty(len(alphas))
    for i, a in enumerate(alphas):
        ok = ~np.isnan(a)
        y, zz = a[ok], z[ok]
        X0 = np.column_stack([np.ones(ok.sum())] + ([control[ok]] if control is not None
                                                     else []))
        M = np.eye(len(y)) - X0 @ np.linalg.pinv(X0)  # annihilator of [1(, control)]
        if scheme == "exposure":
            Zp = np.vstack([zz, rng.permuted(np.tile(zz, (n_perm, 1)), axis=1)])
            R = Zp @ M  # Frisch-Waugh: z residualised on [1(, control)], one row per draw
            b = (R @ y) / np.einsum("ij,ij->i", R, R)
        else:
            rz, e = M @ zz, M @ y  # fitted part of y is orthogonal to rz, so it drops out
            Ep = np.vstack([e, rng.permuted(np.tile(e, (n_perm, 1)), axis=1)])
            b = (Ep @ rz) / (rz @ rz)
        out[i] = (1 + np.sum(np.abs(b[1:]) >= np.abs(b[0]) * (1 - 1e-12))) / (n_perm + 1)
    return out


def mde(null_slopes: np.ndarray, alpha: float = ALPHA, power: float = POWER) -> float:
    """(z_{1-alpha/2} + z_power) * sd(null_slopes), sd with ddof = 1."""
    n = NormalDist()
    return (n.inv_cdf(1 - alpha / 2) + n.inv_cdf(power)) * float(np.std(null_slopes, ddof=1))


def t_crit(alpha: float, df: int = T_DF) -> float:
    """Two-sided critical value t_{df, 1 - alpha/2}."""
    return float(_st.t.ppf(1 - alpha / 2, df))


def t_quantile(p: float, df: int = T_DF) -> float:
    return float(_st.t.ppf(p, df))


def mde_t(null_slopes: np.ndarray, alpha: float = ALPHA, power: float = POWER,
          df: int = T_DF) -> float:
    """(t_{df,1-alpha/2} + t_{df,power}) * sd(null_slopes), sd with ddof = 1."""
    return (t_crit(alpha, df) + t_quantile(power, df)) * float(np.std(null_slopes, ddof=1))


def own_size(slopes: np.ndarray, crits: dict[str, float], center: float | None = None
             ) -> dict:
    """In-sample size of the D10 rule on the historical slopes themselves, s = sd(slopes).

    For each named critical value c: `centred_<name>` = share with |b - mean(b)| / s > c,
    `uncentred_<name>` = share with |b| / s > c (the decision rule as applied). Also the excess
    kurtosis of b (Fisher, bias-corrected) and the empirical quantiles at 0.9875 and 0.975 of
    the symmetrised centred distribution +-(b - mean(b)) / s, i.e. the 0.975 and 0.95 quantiles
    of |b - mean(b)| / s (numpy's default linear interpolation): the empirical analogues of the
    two-sided criticals at 0.025 and 0.05. With `center` (the frozen 378-window mean),
    `centred_frozen_<name>` = share with |b - center| / s > c is added. Only rates, quantiles
    and kurtosis are returned."""
    b = np.asarray(slopes, dtype=float)
    sd = float(np.std(b, ddof=1))
    cen, unc = np.abs(b - b.mean()) / sd, np.abs(b) / sd
    out: dict = {}
    for name, c in crits.items():
        out[f"centred_{name}"] = float(np.mean(cen > c))
        out[f"uncentred_{name}"] = float(np.mean(unc > c))
        if center is not None:
            out[f"centred_frozen_{name}"] = float(np.mean(np.abs(b - center) / sd > c))
    out["excess_kurtosis"] = float(_st.kurtosis(b, fisher=True, bias=False))
    out["q_0.9875"] = float(np.quantile(cen, 0.975))
    out["q_0.975"] = float(np.quantile(cen, 0.95))
    return out


def _design(z: np.ndarray, control: np.ndarray | None = None) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    cols = [np.ones(len(z)), z] + ([np.asarray(control, dtype=float)] if control is not None
                                   else [])
    return np.column_stack(cols)


def leverage(z: np.ndarray, control: np.ndarray | None = None) -> np.ndarray:
    """Diagonal of the hat matrix of [1, z(, control)]."""
    X = _design(z, control)
    return np.einsum("ij,ji->i", X, np.linalg.pinv(X))


def ols_weights(z: np.ndarray, control: np.ndarray | None = None) -> np.ndarray:
    """w with b_z = w @ alphas: the row of (X'X)^-1 X' for the coefficient on z."""
    return np.linalg.pinv(_design(z, control))[1]


def rank_z(x: np.ndarray) -> np.ndarray:
    """Average ranks (ties averaged), z-scored with population SD (D5 variant a, R12)."""
    r = _st.rankdata(np.asarray(x, dtype=float), method="average")
    return (r - r.mean()) / r.std()


def first_full_month(d: date) -> date:
    return d if d.day == 1 else _add_months(date(d.year, d.month, 1), 1)


def parse_frozen(text: str) -> dict[str, float]:
    """The `- `key` = value` lines of the Frozen values section of power.md, as floats."""
    sec = text.split(FROZEN_HEAD, 1)[1].split("\n## ", 1)[0]
    out = {}
    for line in sec.splitlines():
        if line.startswith("- `") and "` = " in line:
            k, v = line[3:].split("` = ", 1)
            out[k] = float(v.split()[0])
    return out


def load_exposure() -> pl.DataFrame:
    """`ff49, ff49_short, z_delegation, z_aioe` for Design B (nulls kept; run_power drops)."""
    from aideleg.benchmarks import benchmark_ff49

    ex = pl.read_parquet(DERIVED / "exposure_ff49.parquet").filter(pl.col("design") == "B")
    bench = benchmark_ff49().select("ff49", "z_aioe")
    return ex.select("ff49", "ff49_short", "z_delegation").join(
        bench, on="ff49", how="left").sort("ff49")


def _fmt_windows(w: list[tuple[date, date]]) -> str:
    return f"{len(w)} ({w[0][0]} -> {w[0][1]} ... {w[-1][0]} -> {w[-1][1]})"


def _write(out: Path, block: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    gen = f"{BEGIN}\n{block}\n{FINISH}"
    if out.exists() and BEGIN in (old := out.read_text()) and FINISH in old:
        head, rest = old.split(BEGIN, 1)
        tail = rest.split(FINISH, 1)[1]
        out.write_text(head + gen + tail)
        return
    out.write_text("# Power analysis for H5 and H5b (pre-seal history)\n\n" + gen +
                   "\n\n## Interpretation\n\n(to be written from the numbers above)\n")


def run_power(out: Path = OUT) -> dict:
    """Run the H5/H5b power analysis on pre-seal history and write `out`."""
    expo = load_exposure()
    returns, factors = _load_returns()
    names = [c for c in returns.columns if c != "date"]
    if sorted(expo["ff49_short"].to_list()) != sorted(names):
        raise ValueError("exposure industries do not match the FF49 return columns")
    expo = expo.with_columns(pl.col("ff49_short").cast(pl.Enum(names))).sort("ff49_short")
    null_z = expo.filter(pl.col("z_delegation").is_null() | pl.col("z_aioe").is_null())
    dropped_z = null_z["ff49_short"].cast(pl.String).to_list()
    keep = expo.filter(pl.col("z_delegation").is_not_null() & pl.col("z_aioe").is_not_null())
    keep_names = keep["ff49_short"].cast(pl.String).to_list()
    z = keep["z_delegation"].to_numpy()
    c = keep["z_aioe"].to_numpy()

    windows = historical_windows()
    A = _alpha_matrix(windows, returns, factors, keep_names)
    # slopes via the public (tested) function; conventional SEs only as a cross-check
    h5 = np.column_stack([slope_null_distribution(z, windows, alphas=A),
                          [_cross_section(a, z, None)[1] for a in A]])
    h5b = np.column_stack([slope_null_distribution(z, windows, alphas=A, control=c),
                           [_cross_section(a, z, c)[1] for a in A]])
    rng = np.random.default_rng(SEED)
    p_h5 = ri_pvalues(A, z, None, N_PERM, rng)
    p_h5b = ri_pvalues(A, z, c, N_PERM, rng)
    p_h5b_fl = ri_pvalues(A, z, c, N_PERM, rng, scheme="freedman_lane")
    missing = np.isnan(A)
    idx_non = list(range(0, len(windows), WINDOW_MONTHS))

    def stats(res: np.ndarray, idx: list[int]) -> dict:
        s = res[idx, 0]
        return {"n": len(idx), "sd": float(np.std(s, ddof=1)), "mde": mde(s),
                "median_ols_se": float(np.median(res[idx, 1]))}

    offsets = [stats(h5, list(range(o, len(windows), WINDOW_MONTHS)))["sd"]
               for o in range(WINDOW_MONTHS)]
    offsets_b = [stats(h5b, list(range(o, len(windows), WINDOW_MONTHS)))["sd"]
                 for o in range(WINDOW_MONTHS)]
    all_idx = list(range(len(windows)))
    r = {"h5_overlap": stats(h5, all_idx), "h5_nonoverlap": stats(h5, idx_non),
         "h5b_overlap": stats(h5b, all_idx), "h5b_nonoverlap": stats(h5b, idx_non)}
    pearson = float(np.corrcoef(z, c)[0, 1])
    spearman = float(keep.select(pl.corr("z_delegation", "z_aioe", method="spearman")).item())
    res = {
        "n_industries": len(keep_names), "dropped_industries_null_z": dropped_z,
        "n_windows_overlap": len(windows), "n_windows_nonoverlap": len(idx_non),
        "first_window": windows[0], "last_window": windows[-1],
        "max_return_date": max(returns["date"].max(), factors["date"].max()),
        "industry_window_drops": int(missing.sum()),
        "windows_with_drops": int(missing.any(axis=1).sum()),
        "min_industries_in_window": int((~missing).sum(axis=1).min()),
        "pearson_aioe_delegation": pearson, "spearman_aioe_delegation": spearman,
        "vif": 1 / (1 - pearson**2),
        "nonoverlap_offset_sd_h5": (min(offsets), float(np.median(offsets)), max(offsets)),
        "nonoverlap_offset_sd_h5b": (min(offsets_b), float(np.median(offsets_b)),
                                     max(offsets_b)),
    }
    for hyp, p in (("h5", p_h5), ("h5b", p_h5b), ("h5b_fl", p_h5b_fl)):
        for scheme, idx in (("overlap", all_idx), ("nonoverlap", idx_non)):
            for lvl in (0.025, 0.05):
                res[f"ri_reject_{hyp}_{scheme}_{lvl}"] = float(np.mean(p[idx] <= lvl))
    res["n_perm"] = N_PERM
    for k, v in r.items():
        res[f"sd_{k}"], res[f"mde_{k}"], res[f"ols_se_{k}"] = v["sd"], v["mde"], v["median_ols_se"]
    res.update(_task15b(A, h5[:, 0], h5b[:, 0], z, c, keep_names, idx_non, returns, factors))
    _write(out, _block(res, windows, idx_non))
    return res


def _task15b(A, b5, b5b, z, c, names, idx_non, returns, factors) -> dict:
    """Referee items C1-C5: t_21 criticals and MDEs, D10 own-size diagnostics, frozen mean
    slopes, the 1963 start, leverage, and the R12/R13 null scales. Only dispersion, rates,
    quantiles, kurtosis, leverage and the frozen mean slopes are produced."""
    out: dict = {}
    crits = {f"{kind}_{lvl}": (NormalDist().inv_cdf(1 - lvl / 2) if kind == "n" else t_crit(lvl))
             for kind in ("n", "t") for lvl in HOLM_LEVELS}
    out["crits"] = crits
    for hyp, b in (("h5", b5), ("h5b", b5b)):
        out[f"mde_t_{hyp}_overlap"] = mde_t(b)
        out[f"mde_t_{hyp}_nonoverlap"] = mde_t(b[idx_non])
        bbar = float(np.mean(b))  # C3: frozen; its sign is not interpreted
        out[f"bbar_{hyp}"] = bbar
        out[f"size_{hyp}_overlap"] = own_size(b, crits, center=bbar)
        out[f"size_{hyp}_nonoverlap"] = own_size(b[idx_non], crits, center=bbar)
    # C5: leverage and OLS weights over the industries used
    out["leverage_h5"] = dict(zip(names, map(float, leverage(z)), strict=True))
    out["leverage_h5b"] = dict(zip(names, map(float, leverage(z, c)), strict=True))
    out["weight_h5"] = dict(zip(names, map(float, ols_weights(z)), strict=True))
    out["weight_h5b"] = dict(zip(names, map(float, ols_weights(z, c)), strict=True))
    # C5: R12 (standardised ranks of z_delegation; z_aioe unchanged) and R13 (drop Softw,
    # z not re-standardised), same windows, same code
    zr = rank_z(z)
    keep = np.array([n != SOFTW for n in names])
    variants = {
        "h5_r12": slope_null_distribution(zr, [None] * len(A), alphas=A),
        "h5b_r12": slope_null_distribution(zr, [None] * len(A), alphas=A, control=c),
        "h5_r13": slope_null_distribution(z[keep], [None] * len(A), alphas=A[:, keep]),
        "h5b_r13": slope_null_distribution(z[keep], [None] * len(A), alphas=A[:, keep],
                                           control=c[keep]),
    }
    for key, b in variants.items():
        sz = own_size(b, crits)
        out[f"sd_{key}_overlap"] = float(np.std(b, ddof=1))
        out[f"mde_t_{key}_overlap"] = mde_t(b)
        out[f"q_{key}"] = (sz["q_0.9875"], sz["q_0.975"])
        out[f"bbar_{key}"] = float(np.mean(b))
    out["rank_corr_r12"] = float(np.corrcoef(zr, z)[0, 1])
    # C4: windows from the first full month of daily FF5 (+ UMD) data, and a row from the first
    # month in which all 49 industries have returns
    f0 = first_full_month(factors["date"].min())
    first_all = first_full_month(max(
        returns.filter(pl.col(n).is_not_null())["date"].min() for n in names))
    for tag, first in (("1963", f0), ("all49", max(f0, first_all))):
        w = historical_windows(first)
        Aw = _alpha_matrix(w, returns, factors, names)
        idx = list(range(0, len(w), WINDOW_MONTHS))
        miss = np.isnan(Aw)
        out[f"start_{tag}"] = first
        out[f"windows_{tag}"] = (len(w), len(idx))
        out[f"drops_{tag}"] = (int(miss.sum()), int(miss.any(axis=1).sum()),
                               sorted({names[j] for j in np.where(miss.any(axis=0))[0]}))
        for hyp, ctl in (("h5", None), ("h5b", c)):
            b = slope_null_distribution(z, w, alphas=Aw, control=ctl)
            for sch, ii in (("overlap", list(range(len(w)))), ("nonoverlap", idx)):
                out[f"sd_{hyp}_{tag}_{sch}"] = float(np.std(b[ii], ddof=1))
                out[f"mde_{hyp}_{tag}_{sch}"] = mde(b[ii])
                out[f"mde_t_{hyp}_{tag}_{sch}"] = mde_t(b[ii])
    return out


def _block(res: dict, windows, idx_non) -> str:
    k = NormalDist().inv_cdf(1 - ALPHA / 2) + NormalDist().inv_cdf(POWER)
    pp = 100.0
    rows = []
    for hyp, label in (("h5", "H5: alpha on z_delegation"),
                       ("h5b", "H5b: alpha on z_delegation + z_aioe (coef on z_delegation)")):
        for scheme, name in (("overlap", "overlapping (monthly step)"),
                             ("nonoverlap", "non-overlapping")):
            key = f"{hyp}_{scheme}"
            n = res["n_windows_overlap"] if scheme == "overlap" else res["n_windows_nonoverlap"]
            rows.append(f"| {label} | {name} | {n} | {res[f'sd_{key}'] * pp:.2f} | "
                        f"{res[f'mde_{key}'] * pp:.2f} | {res[f'ols_se_{key}'] * pp:.2f} |")
    label = {"h5": "H5 (permute z)", "h5b": "H5b (permute z, z_aioe fixed)",
             "h5b_fl": "H5b (Freedman-Lane, permute residuals)"}
    ri_rows = [f"| {label[hyp]} | {scheme} | "
               f"{res['n_windows_' + ('overlap' if scheme == 'overlapping' else 'nonoverlap')]}"
               f" | {res[f'ri_reject_{hyp}_{key}_0.025']:.3f} | "
               f"{res[f'ri_reject_{hyp}_{key}_0.05']:.3f} |"
               for hyp in ("h5", "h5b", "h5b_fl")
               for scheme, key in (("overlapping", "overlap"), ("non-overlapping", "nonoverlap"))]
    lo, med, hi = res["nonoverlap_offset_sd_h5"]
    lob, medb, hib = res["nonoverlap_offset_sd_h5b"]
    nov = [windows[i] for i in idx_non]
    dz = ", ".join(res["dropped_industries_null_z"]) or "none"
    lines = [
        "Generated by `uv run python -m aideleg.power`. Do not edit inside this block.",
        "",
        "AEI data are conversations matched to O*NET tasks; nothing here says anything about "
        "job risk or displacement in the labour market.",
        "",
        "## Set-up",
        "",
        f"- Returns: FF49 daily value-weighted industry returns and FF5 + UMD daily factors, "
        f"read through the sealed loaders with `end = {END}`. Latest date read: "
        f"{res['max_return_date']} (seal {SEAL_DATE}).",
        "- Alphas: per industry and window, daily OLS of excess return on FF5 + UMD; "
        "intercept x 252 (decimal per year; tables below in percentage points).",
        f"- Exposure held fixed: Design B `z_delegation` and `z_aioe` (population-SD "
        f"z-scores across FF49). Industries used: {res['n_industries']}; dropped for a null "
        f"z: {dz}.",
        f"- Windows: {WINDOW_MONTHS} months (the Design B window length), stepped monthly "
        f"from {FIRST_START}, last window ending on or before {END}.",
        f"  - overlapping: {_fmt_windows(windows)}",
        f"  - non-overlapping (offset 0): {_fmt_windows(nov)}",
        f"- Missing returns: {res['industry_window_drops']} industry-window drops in "
        f"{res['windows_with_drops']} of {res['n_windows_overlap']} windows (fewest "
        f"industries in a window: {res['min_industries_in_window']}).",
        f"- Collinearity (across the {res['n_industries']} industries): Pearson(z_aioe, "
        f"z_delegation) = {res['pearson_aioe_delegation']:.3f}, Spearman = "
        f"{res['spearman_aioe_delegation']:.3f}, VIF = {res['vif']:.2f}.",
        f"- MDE = (z_(1-{ALPHA}/2) + z_{POWER}) x sd = {k:.4f} x sd; alpha = {ALPHA} is "
        f"Holm's first step over {{H5, H5b}}, power = {POWER}.",
        "",
        "## Slope dispersion and MDE",
        "",
        "Units: annualised alpha, percentage points per 1 SD of exposure. Only the "
        "dispersion of the historical slopes is reported; their level is not a finding.",
        "",
        "| hypothesis | windows | n | sd of slope | MDE | median within-window OLS SE |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
        f"Non-overlapping sd across all {WINDOW_MONTHS} start offsets (min / median / max, "
        f"pp): H5 {lo * pp:.2f} / {med * pp:.2f} / {hi * pp:.2f}; H5b {lob * pp:.2f} / "
        f"{medb * pp:.2f} / {hib * pp:.2f}.",
        "",
        "## Size of the specified randomisation-inference test under no relation",
        "",
        f"Each historical window run through the confirmatory RI test as specified: exposure "
        f"(`z_delegation`) permuted across industries, {res['n_perm']:,} permutations per "
        f"window and row (seed `SEED` = {SEED}), two-sided permutation p-value of the "
        f"slope; for H5b `z_aioe` stays in place. The spec does not say how H5b's control "
        f"is handled, so the Freedman-Lane scheme (residuals of alpha on [1, z_aioe] "
        f"permuted) is shown beside it. Share of windows rejecting (nominal level in the "
        f"header). Only rejection rates are reported.",
        "",
        "| hypothesis | windows | n | reject at 0.025 | reject at 0.05 |",
        "|---|---|---|---|---|",
        *ri_rows,
        "",
        f"Reference only (decided at Task 15): the plan file's plausibility threshold is "
        f"{PLAUSIBILITY_PP:.0f} pp per 1 SD for the H5 MDE.",
        "",
        *_block_15b(res),
    ]
    return "\n".join(lines)


def frozen_values(res: dict) -> dict[str, float]:
    """The numbers the confirmatory script (aideleg.confirm_h5) freezes, keyed as in power.md.
    `crit_<v>_<lvl>` = max(t_21 critical, empirical centred quantile) for variant v, the most
    conservative of the two calibrations (referee P1); it multiplies `s_<v>`."""
    f = {"t21_0.025": t_crit(0.025), "t21_0.05": t_crit(0.05)}
    for hyp in ("h5", "h5b"):
        f[f"s_{hyp}"] = res[f"sd_{hyp}_overlap"]
        f[f"bbar_{hyp}"] = res[f"bbar_{hyp}"]
        sz = res[f"size_{hyp}_overlap"]
        f[f"q_{hyp}_0.9875"], f[f"q_{hyp}_0.975"] = sz["q_0.9875"], sz["q_0.975"]
        for var in ("r12", "r13"):
            key = f"{hyp}_{var}"
            f[f"s_{key}"] = res[f"sd_{key}_overlap"]
            f[f"q_{key}_0.9875"], f[f"q_{key}_0.975"] = res[f"q_{key}"]
            f[f"bbar_{key}"] = res[f"bbar_{key}"]
    for v in ("h5", "h5b", "h5_r12", "h5b_r12", "h5_r13", "h5b_r13"):
        f[f"crit_{v}_0.025"] = max(f["t21_0.025"], f[f"q_{v}_0.9875"])
        f[f"crit_{v}_0.05"] = max(f["t21_0.05"], f[f"q_{v}_0.975"])
    return f


def null_scales(A: np.ndarray, z: np.ndarray, c: np.ndarray, names: list[str]
                ) -> dict[str, float]:
    """The `frozen_values` keys recomputed from a windows x industries alpha matrix over
    `names` (used by `aideleg.confirm_h5` when an industry drops out of the confirmatory
    window). Same estimators as `run_power`; R13 drops Softw if present."""
    nw = len(A)
    zr, keep = rank_z(z), np.array([n != SOFTW for n in names])
    slopes = {
        "h5": slope_null_distribution(z, [None] * nw, alphas=A),
        "h5b": slope_null_distribution(z, [None] * nw, alphas=A, control=c),
        "h5_r12": slope_null_distribution(zr, [None] * nw, alphas=A),
        "h5b_r12": slope_null_distribution(zr, [None] * nw, alphas=A, control=c),
        "h5_r13": slope_null_distribution(z[keep], [None] * nw, alphas=A[:, keep]),
        "h5b_r13": slope_null_distribution(z[keep], [None] * nw, alphas=A[:, keep],
                                           control=c[keep]),
    }
    f = {"t21_0.025": t_crit(0.025), "t21_0.05": t_crit(0.05)}
    for v, b in slopes.items():
        sz = own_size(b, {})
        f[f"s_{v}"] = float(np.std(b, ddof=1))
        f[f"q_{v}_0.9875"], f[f"q_{v}_0.975"] = sz["q_0.9875"], sz["q_0.975"]
        f[f"bbar_{v}"] = float(np.mean(b))
        f[f"crit_{v}_0.025"] = max(f["t21_0.025"], f[f"q_{v}_0.9875"])
        f[f"crit_{v}_0.05"] = max(f["t21_0.05"], f[f"q_{v}_0.975"])
    return f


def _block_15b(res: dict) -> list[str]:
    pp = 100.0
    cr = res["crits"]
    kt = t_crit(ALPHA) + t_quantile(POWER)
    rows_c1 = []
    for hyp, label in (("h5", "H5"), ("h5b", "H5b")):
        for sch, name in (("overlap", "overlapping"), ("nonoverlap", "non-overlapping")):
            sd = res[f"sd_{hyp}_{sch}"]
            rows_c1.append(
                f"| {label} | {name} | {sd * pp:.3f} | {cr['n_0.025'] * sd * pp:.3f} | "
                f"{cr['t_0.025'] * sd * pp:.3f} | {cr['n_0.05'] * sd * pp:.3f} | "
                f"{cr['t_0.05'] * sd * pp:.3f} | {res[f'mde_{hyp}_{sch}'] * pp:.2f} | "
                f"{res[f'mde_t_{hyp}_{sch}'] * pp:.2f} |")
    rows_c2 = []
    for hyp, label in (("h5", "H5"), ("h5b", "H5b")):
        for sch, name, n in (("overlap", "overlapping", res["n_windows_overlap"]),
                             ("nonoverlap", "non-overlapping", res["n_windows_nonoverlap"])):
            o = res[f"size_{hyp}_{sch}"]
            rate = " | ".join(f"{o[f'{k}_{c}_{lvl}']:.3f}"
                              for k in ("centred", "centred_frozen", "uncentred")
                              for lvl in HOLM_LEVELS for c in ("n", "t"))
            rows_c2.append(f"| {label} | {name} | {n} | {o['excess_kurtosis']:.2f} | "
                           f"{o['q_0.9875']:.3f} | {o['q_0.975']:.3f} | {rate} |")
    rows_c4 = []
    for tag in ("1963", "all49"):
        nw, nn = res[f"windows_{tag}"]
        for hyp, label in (("h5", "H5"), ("h5b", "H5b")):
            for sch, name, n in (("overlap", "overlapping", nw), ("nonoverlap", "non-overl.", nn)):
                rows_c4.append(
                    f"| {res[f'start_{tag}']} | {label} | {name} | {n} | "
                    f"{res[f'sd_{hyp}_{tag}_{sch}'] * pp:.2f} | "
                    f"{res[f'mde_{hyp}_{tag}_{sch}'] * pp:.2f} | "
                    f"{res[f'mde_t_{hyp}_{tag}_{sch}'] * pp:.2f} |")
    drops = [f"  - from {res[f'start_{t}']}: {res[f'windows_{t}'][0]} overlapping windows, "
             f"{res[f'drops_{t}'][0]} industry-window drops in {res[f'drops_{t}'][1]} windows "
             f"(industries: {', '.join(res[f'drops_{t}'][2]) or 'none'})"
             for t in ("1963", "all49")]
    lev5, lev5b, w5, w5b = (res[k] for k in ("leverage_h5", "leverage_h5b", "weight_h5",
                                              "weight_h5b"))
    order = sorted(lev5, key=lambda n: -lev5[n])
    rows_c5 = [f"| {n} | {lev5[n]:.3f} | {lev5b[n]:.3f} | {w5[n]:+.4f} | {w5b[n]:+.4f} |"
               for n in order]

    def share(w: dict) -> float:
        return abs(w[SOFTW]) / sum(abs(v) for v in w.values())

    rows_var = []
    for hyp, label in (("h5", "H5"), ("h5b", "H5b")):
        for var, vname in (("r12", "R12 standardised ranks"), ("r13", "R13 drop Softw")):
            key = f"{hyp}_{var}"
            sd = res[f"sd_{key}_overlap"]
            q1, q2 = res[f"q_{key}"]
            rows_var.append(
                f"| {label} | {vname} | {sd * pp:.3f} | {q1:.3f} | {q2:.3f} | "
                f"{cr['t_0.025'] * sd * pp:.3f} | {cr['t_0.05'] * sd * pp:.3f} | "
                f"{max(cr['t_0.025'], q1) * sd * pp:.3f} | {max(cr['t_0.05'], q2) * sd * pp:.3f}"
                f" | {res[f'mde_t_{key}_overlap'] * pp:.2f} |")
    fz = frozen_values(res)
    has_softw = SOFTW in lev5
    softw = (f"Softw: leverage {lev5[SOFTW]:.3f} (H5), {lev5b[SOFTW]:.3f} (H5b); OLS weight "
             f"{w5[SOFTW]:+.4f} (H5), {w5b[SOFTW]:+.4f} (H5b), i.e. {share(w5):.1%} and "
             f"{share(w5b):.1%} of the sum of |weights|. Mean leverage is 2/n (H5) and 3/n "
             f"(H5b)." if has_softw else "Softw is not among the industries used.")
    return [
        f"## Small-sample criticals (t_{T_DF})",
        "",
        f"s rests on about 22 independent 17-month windows, so the normal criticals are "
        f"replaced by t with nu = {T_DF} (fixed): t_{T_DF},0.9875 = {cr['t_0.025']:.4f} "
        f"(Holm step 0.025) and t_{T_DF},0.975 = {cr['t_0.05']:.4f} (step 0.05), against "
        f"{cr['n_0.025']:.4f} and {cr['n_0.05']:.4f} for the normal. MDE_t = "
        f"(t_{T_DF},0.9875 + t_{T_DF},0.80) x s = {kt:.4f} x s. Critical values for |b| in pp.",
        "",
        "| hypothesis | windows | s | normal crit 0.025 | t_21 crit 0.025 | normal crit 0.05 | "
        "t_21 crit 0.05 | MDE normal | MDE t_21 |",
        "|---|---|---|---|---|---|---|---|---|",
        *rows_c1,
        "",
        "## Own size of the D10 rule on the historical windows",
        "",
        "In-sample: each window's slope b is scored against the s of the same window set. "
        "Centred: |b - mean(b)| / s > crit. Uncentred: |b| / s > crit, the decision rule as "
        "applied. q_0.9875 and q_0.975 are the empirical quantiles of the symmetrised centred "
        "distribution +-(b - mean(b)) / s (equivalently the 0.975 and 0.95 quantiles of "
        "|b - mean(b)| / s), the empirical counterparts of the 0.025 and 0.05 two-sided "
        "criticals. Kurtosis is excess (Fisher, bias-corrected). Two centrings: 'centred "
        "(own mean)' uses the mean of the window set in the row (378 or 23 windows); 'centred "
        "on the frozen b-bar' uses the frozen mean of the 378 overlapping windows (the "
        "`bbar_*` of the Frozen values) for both rows, so the two coincide for the "
        "overlapping rows. s is always the sd of the row's own window set. Only rates, "
        "quantiles and kurtosis are reported.",
        "",
        "| hypothesis | windows | n | excess kurtosis | q_0.9875 | q_0.975 | "
        "centred (own mean) 0.025 normal | 0.025 t_21 | 0.05 normal | 0.05 t_21 | "
        "centred on the frozen b-bar 0.025 normal | 0.025 t_21 | 0.05 normal | 0.05 t_21 | "
        "uncentred 0.025 normal | 0.025 t_21 | 0.05 normal | 0.05 t_21 |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        *rows_c2,
        "",
        "## Start-date robustness",
        "",
        "Same procedure with windows stepped monthly from the first full month of daily FF5 "
        "data (the momentum file starts earlier, so FF5 binds), and from the first month in "
        "which every industry has daily returns. An industry with a missing return in a "
        "window is dropped from that window's cross-section (z not re-standardised).",
        *drops,
        "",
        "| first window | hypothesis | windows | n | s | MDE normal | MDE t_21 |",
        "|---|---|---|---|---|---|---|",
        *rows_c4,
        "",
        "## Leverage and OLS weights",
        "",
        "h_j = diagonal of the hat matrix of [1, z_delegation] (H5) and [1, z_delegation, "
        "z_aioe] (H5b); weight w_j is the industry's coefficient in b = sum_j w_j alpha_j. "
        + softw,
        "",
        "| industry | h_j H5 | h_j H5b | w_j H5 | w_j H5b |",
        "|---|---|---|---|---|",
        *rows_c5,
        "",
        "## Null scales for R12 and R13",
        "",
        f"Same 378 overlapping windows and code as the primary. R12: `z_delegation` replaced "
        f"by its standardised average ranks (Pearson with `z_delegation` "
        f"{res['rank_corr_r12']:.3f}); `z_aioe` unchanged in H5b. R13: Softw dropped, 48 "
        f"industries, z not re-standardised. Criticals for |b| in pp; 'max' columns use "
        f"max(t_{T_DF} critical, empirical centred quantile) x s.",
        "",
        "| hypothesis | variant | s | q_0.9875 | q_0.975 | t_21 crit 0.025 | t_21 crit 0.05 | "
        "max crit 0.025 | max crit 0.05 | MDE t_21 |",
        "|---|---|---|---|---|---|---|---|---|---|",
        *rows_var,
        "",
        FROZEN_HEAD,
        "",
        "Full precision (repr). Read by `aideleg.confirm_h5`, whose constants must equal "
        "these (tested). s = sd of the 378 overlapping slopes (ddof = 1); bbar = their mean "
        "(frozen for the b = bbar null and the interpretive check; its sign is not "
        "interpreted); q = empirical "
        "centred quantiles above; crit = max(t21, q) for the same level.",
        "",
        *[f"- `{k}` = {v!r}" for k, v in fz.items()],
    ]


def main() -> int:
    res = run_power()
    for k in ("h5_overlap", "h5_nonoverlap", "h5b_overlap", "h5b_nonoverlap"):
        print(f"{k:16s} sd {res[f'sd_{k}'] * 100:6.2f} pp  MDE {res[f'mde_{k}'] * 100:6.2f} pp")
    print(f"windows: {res['n_windows_overlap']} overlapping, {res['n_windows_nonoverlap']} "
          f"non-overlapping; latest date read {res['max_return_date']}")
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
