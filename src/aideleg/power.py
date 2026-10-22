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

Integrity. Returns are read only through the French loaders with end = 2022-11-29, and every
row is re-checked against the seal. The historical slopes themselves (their mean or sign) are
not a finding and are never reported: only their dispersion, the window counts and the MDEs.
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
PLAUSIBILITY_PP = 5.0  # spec rule, decided by Ajai at Task 15; reported for reference only


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
    _write(out, _block(res, windows, idx_non))
    return res


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
        f"Reference only (decided at Task 15): the spec's plausibility threshold is "
        f"{PLAUSIBILITY_PP:.0f} pp per 1 SD for the H5 MDE.",
    ]
    return "\n".join(lines)


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
