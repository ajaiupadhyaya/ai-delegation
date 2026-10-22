"""Confirmatory test of H5 and H5b (PAP §3). Run ONCE, after the git tag `pap-v1` exists:

    uv run python -m aideleg.confirm_h5

It writes `docs/results/confirmatory_h5.md` and refuses to overwrite it. The output is committed
unedited (PAP single-run protocol). Every number this script freezes was produced pre-seal by
`aideleg.power` and is listed in the Frozen values section of `docs/pap/power.md`; a test
asserts the constants below equal that list. This file's git blob hash is recorded in the PAP.

Steps.
1. Refuse unless `pap-v1` exists and the output file does not; check the Design B exposure
   vector against its frozen SHA-256 (PAP §9.3).
2. Load FF49 daily value-weighted returns and FF5 + UMD daily factors through the sealed loaders,
   end = 2026-08-31, and keep the window 2025-04-01 -> 2026-08-31.
3. Alphas: `aideleg.power.window_alphas` (daily OLS on FF5 + UMD, intercept x 252). An
   industry with any missing return is dropped; z is not re-standardised; the null scales are
   then recomputed on the kept industries from pre-seal history with the same code
   (`aideleg.power.null_scales`, returns read with end = 2022-11-29).
4. Slopes b for H5 ([1, z_delegation]) and H5b ([1, z_delegation, z_aioe]), and for R12
   (standardised ranks of z_delegation) and R13 (Softw dropped). T = b / s_v.
5. Primary decision (D10 with referee rulings P1, P5, P14): critical c_v,L = max(t_21 critical,
   empirical centred quantile) for Holm level L; Holm over {H5, H5b} at family-wise 0.05, ordered
   by the t_21 p-value 2(1 - F_21(|T|)). Co-condition: "delegation exposure is priced" requires
   rejection of the primary AND of its R13 variant at the same Holm level; if only the primary
   rejects, the fixed wording is "driven by Softw". If the primary rejects but
   |b - bbar| / s < c, the fixed wording adds "not distinguishable from the 1990-2022 pattern
   for this exposure vector". Intervals: b +- c_v,0.05 * s_v and b +- c_v,0.025 * s_v.
6. Secondary, never used for the decision: RI permuting z_delegation (H5, H5b with z_aioe in
   place) and Freedman-Lane RI for H5b, 10,000 permutations each from one
   `numpy.random.default_rng(SEED)` consumed in that order; conventional OLS with HC3 SEs.

AEI data are conversations matched to O*NET tasks; nothing here says anything about job risk or
displacement in the labour market.
"""

import hashlib
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy import stats as _st

from aideleg import power
from aideleg.config import PAP_TAG, ROOT, SEED
from aideleg.market import seal
from aideleg.market.french import load_factors, load_industry_returns

WINDOW = (date(2025, 4, 1), date(2026, 8, 31))
OUT = ROOT / "docs/results/confirmatory_h5.md"
EXPOSURE_SHA256 = "bddc49d49b9565bba8daa8bc6fdb709043a6007090b9e7faf7dda1001229ac36"
N_PERM = 10_000
T_DF = 21
LEVELS = (0.025, 0.05)
VARIANTS = ("h5", "h5b", "h5_r12", "h5b_r12", "h5_r13", "h5b_r13")
LABEL = {"h5": "H5", "h5b": "H5b", "h5_r12": "H5 R12 (ranks)", "h5b_r12": "H5b R12 (ranks)",
         "h5_r13": "H5 R13 (drop Softw)", "h5b_r13": "H5b R13 (drop Softw)"}

# Copied from the Frozen values section of docs/pap/power.md (tested equal).
FROZEN: dict[str, float] = {
    "t21_0.025": 2.413845016599001,
    "t21_0.05": 2.0796138447276795,
    "s_h5": 0.022709785806829905,
    "bbar_h5": 0.01650391358632771,
    "q_h5_0.9875": 2.08027722179776,
    "q_h5_0.975": 1.896096850699846,
    "s_h5_r12": 0.02211139470714751,
    "q_h5_r12_0.9875": 1.9961589827719277,
    "q_h5_r12_0.975": 1.8109235160395372,
    "s_h5_r13": 0.03195141979632061,
    "q_h5_r13_0.9875": 1.9840047664550942,
    "q_h5_r13_0.975": 1.8881504350635059,
    "s_h5b": 0.02560409470770698,
    "bbar_h5b": 0.01216949247017634,
    "q_h5b_0.9875": 2.13084415252217,
    "q_h5b_0.975": 1.862988779992977,
    "s_h5b_r12": 0.02981733257175669,
    "q_h5b_r12_0.9875": 2.3039239552905793,
    "q_h5b_r12_0.975": 1.9664328516491718,
    "s_h5b_r13": 0.037132757280610024,
    "q_h5b_r13_0.9875": 2.166482901101018,
    "q_h5b_r13_0.975": 1.962325225285184,
    "crit_h5_0.025": 2.413845016599001,
    "crit_h5_0.05": 2.0796138447276795,
    "crit_h5b_0.025": 2.413845016599001,
    "crit_h5b_0.05": 2.0796138447276795,
    "crit_h5_r12_0.025": 2.413845016599001,
    "crit_h5_r12_0.05": 2.0796138447276795,
    "crit_h5b_r12_0.025": 2.413845016599001,
    "crit_h5b_r12_0.05": 2.0796138447276795,
    "crit_h5_r13_0.025": 2.413845016599001,
    "crit_h5_r13_0.05": 2.0796138447276795,
    "crit_h5b_r13_0.025": 2.413845016599001,
    "crit_h5b_r13_0.05": 2.0796138447276795,
}


def holm(p: dict[str, float]) -> dict[str, float | None]:
    """Holm over two hypotheses at family-wise 0.05: the Holm level at which each is rejected
    (0.025 or 0.05), or None."""
    (k1, p1), (k2, p2) = sorted(p.items(), key=lambda kv: kv[1])
    if p1 > LEVELS[0]:
        return {k1: None, k2: None}
    return {k1: LEVELS[0], k2: LEVELS[1] if p2 <= LEVELS[1] else None}


def _p_t(T: float) -> float:
    return float(2 * _st.t.sf(abs(T), T_DF))


def decide(b: dict[str, float], fz: dict[str, float]) -> dict:
    """The decision from the slopes `b` (keys VARIANTS, decimal) and the frozen values `fz`.

    Holm orders H5 and H5b by their t_21 p-values; a hypothesis rejected at Holm level L counts
    as rejected under the primary only if also |T| > c_L (c = max(t_21, empirical quantile)).
    With the frozen values c = t_21 for every variant, so this is the t_21 test itself."""
    T = {v: b[v] / fz[f"s_{v}"] for v in VARIANTS}
    p = {v: _p_t(T[v]) for v in VARIANTS}
    lvl = holm({"H5": p["h5"], "H5b": p["h5b"]})
    passes = {hyp: lvl[hyp] is not None and abs(T[v]) > fz[f"crit_{v}_{lvl[hyp]}"]
              for hyp, v in (("H5", "h5"), ("H5b", "h5b"))}
    first = "H5" if p["h5"] <= p["h5b"] else "H5b"
    if not passes[first]:  # Holm stops at the first step
        passes = {"H5": False, "H5b": False}
    primary, co, wording, ci = {}, {}, {}, {}
    for hyp, v in (("H5", "h5"), ("H5b", "h5b")):
        L = lvl[hyp]
        ok = passes[hyp]
        primary[hyp] = L if ok else None
        r13 = f"{v}_r13"
        co[hyp] = bool(ok and abs(T[r13]) > fz[f"crit_{r13}_{L}"])
        for lv in LEVELS:
            c = fz[f"crit_{v}_{lv}"] * fz[f"s_{v}"]
            ci[(hyp, lv)] = (b[v] - c, b[v] + c)
        mde = (fz["t21_0.025"] + float(_st.t.ppf(0.80, T_DF))) * fz[f"s_{v}"]
        if not ok:
            lo, hi = ci[(hyp, 0.05)]
            wording[hyp] = (f"{hyp} is not rejected. Interval [{lo * 100:.2f}, {hi * 100:.2f}] pp "
                            f"per 1 SD; the test had 80% power only against |b| >= "
                            f"{mde * 100:.2f} pp per 1 SD (MDE at Holm level 0.025).")
            continue
        if co[hyp]:
            w = (f"{hyp} is rejected at Holm level {L}, and so is its R13 variant (Softw "
                 f"dropped): delegation exposure is priced in this window.")
        else:
            w = (f"{hyp} is rejected at Holm level {L}, but its R13 variant (Softw dropped) is "
                 f"not: the result is driven by Softw.")
        if abs(b[v] - fz[f"bbar_{v}"]) / fz[f"s_{v}"] < fz[f"crit_{v}_{L}"]:
            w += (" The slope is not distinguishable from the 1990-2022 pattern for this "
                  "exposure vector.")
        wording[hyp] = w
    return {"T": T, "p_t21": p, "holm_level": lvl, "primary": primary, "co_condition": co,
            "wording": wording, "ci": ci}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (subprocess.CalledProcessError, OSError):
        return "unknown"


def _vector_hash(expo: pl.DataFrame) -> str:
    df = expo.select("ff49", "ff49_short", "z_delegation", "z_aioe")
    return hashlib.sha256(df.write_csv(float_precision=10).encode()).hexdigest()


def _hc3(alphas: np.ndarray, X: np.ndarray) -> tuple[float, float]:
    fit = sm.OLS(alphas, X).fit(cov_type="HC3")
    return float(fit.params[1]), float(fit.bse[1])


def run(out: Path = OUT) -> dict:
    out = Path(out)
    if out.exists():
        raise FileExistsError(f"{out} exists; the confirmatory test is run once")
    if not seal.pap_frozen():
        raise seal.SealedPeriodError(f"the git tag {PAP_TAG} does not exist; not run")
    expo = power.load_exposure()
    if expo.height != 49 or expo.null_count().sum_horizontal().item():
        raise ValueError("the Design B exposure vector must have 49 rows and no nulls")
    if (h := _vector_hash(expo)) != EXPOSURE_SHA256:
        raise ValueError(f"exposure vector hash {h} != frozen {EXPOSURE_SHA256}")

    returns = load_industry_returns("D", "VW", WINDOW[1])
    factors = load_factors("D", WINDOW[1])
    names = [c for c in returns.columns if c != "date"]
    if sorted(names) != sorted(expo["ff49_short"].to_list()):
        raise ValueError("exposure industries do not match the FF49 return columns")
    expo = expo.with_columns(pl.col("ff49_short").cast(pl.Enum(names))).sort("ff49_short")
    win = [df.filter((pl.col("date") >= WINDOW[0]) & (pl.col("date") <= WINDOW[1]))
           for df in (returns, factors)]
    first, last = (min(d["date"].min() for d in win), max(d["date"].max() for d in win))
    alphas_all = power.window_alphas(returns, factors, *WINDOW).to_numpy().astype(float)
    ok = ~np.isnan(alphas_all)
    dropped = [n for n, k in zip(names, ok, strict=True) if not k]
    kept = [n for n, k in zip(names, ok, strict=True) if k]
    z = expo["z_delegation"].to_numpy()[ok]
    c = expo["z_aioe"].to_numpy()[ok]
    a = alphas_all[ok]

    fz = dict(FROZEN)
    if dropped:  # recompute every null scale on the kept industries from pre-seal history
        hist_r, hist_f = power._load_returns()
        A = power._alpha_matrix(power.historical_windows(), hist_r, hist_f, kept)
        fz = power.null_scales(A, z, c, kept)

    zr = power.rank_z(z)
    keep13 = np.array([n != power.SOFTW for n in kept])
    designs = {
        "h5": (z, None, slice(None)), "h5b": (z, c, slice(None)),
        "h5_r12": (zr, None, slice(None)), "h5b_r12": (zr, c, slice(None)),
        "h5_r13": (z, None, keep13), "h5b_r13": (z, c, keep13),
    }
    b = {}
    for v, (zz, cc, m) in designs.items():
        b[v] = float(power.ols_weights(zz[m], None if cc is None else cc[m]) @ a[m])
    d = decide(b, fz)

    rng = np.random.default_rng(SEED)
    A1 = a[None, :]
    ri = {"h5_exposure": float(power.ri_pvalues(A1, z, None, N_PERM, rng)[0]),
          "h5b_exposure": float(power.ri_pvalues(A1, z, c, N_PERM, rng)[0]),
          "h5b_freedman_lane": float(power.ri_pvalues(A1, z, c, N_PERM, rng,
                                                      scheme="freedman_lane")[0])}
    hc3 = {"h5": _hc3(a, power._design(z)), "h5b": _hc3(a, power._design(z, c))}
    res = {"b": b, "T": d["T"], "decision": d, "ri": ri, "hc3": hc3, "dropped": dropped,
           "frozen_used": fz, "first_date": first, "last_date": last, "n": len(kept),
           "n_days": win[1].height}
    text = _report(res)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("x") as fh:  # never overwrite, even under a race
        fh.write(text)
    return res


def _report(res: dict) -> str:
    d, fz, pp = res["decision"], res["frozen_used"], 100.0
    rows = []
    for v in VARIANTS:
        s = fz[f"s_{v}"]
        rows.append(f"| {LABEL[v]} | {res['b'][v] * pp:.3f} | {s * pp:.3f} | {d['T'][v]:.3f} | "
                    f"{d['p_t21'][v]:.4f} | {fz[f'crit_{v}_0.025']:.4f} | "
                    f"{fz[f'crit_{v}_0.05']:.4f} |")
    dec = []
    for hyp in ("H5", "H5b"):
        lo, hi = d["ci"][(hyp, 0.05)]
        lo2, hi2 = d["ci"][(hyp, 0.025)]
        dec += [f"- **{hyp}.** Holm level reached: {d['holm_level'][hyp]}; primary rejection: "
                f"{d['primary'][hyp] is not None}; R13 co-condition met: {d['co_condition'][hyp]}.",
                f"  - Interval b +- c_0.05 x s: [{lo * pp:.3f}, {hi * pp:.3f}] pp; "
                f"b +- c_0.025 x s: [{lo2 * pp:.3f}, {hi2 * pp:.3f}] pp.",
                f"  - Fixed wording: {d['wording'][hyp]}"]
    interp = [f"- {hyp}: (b - bbar) / s = "
              f"{(res['b'][v] - fz[f'bbar_{v}']) / fz[f's_{v}']:.3f}"
              for hyp, v in (("H5", "h5"), ("H5b", "h5b"))]
    blob = _git("hash-object", str(Path(__file__).resolve()))
    lines = [
        "# Confirmatory test of H5 and H5b",
        "",
        "Generated once by `uv run python -m aideleg.confirm_h5`; committed unedited.",
        "",
        "AEI data are conversations matched to O*NET tasks; nothing here says anything about "
        "job risk or displacement in the labour market.",
        "",
        "## Provenance",
        "",
        f"- Commit: `{_git('rev-parse', 'HEAD')}`; tag `{PAP_TAG}` -> "
        f"`{_git('rev-list', '-n', '1', PAP_TAG)}`.",
        f"- `src/aideleg/confirm_h5.py` blob: `{blob}`.",
        f"- Exposure vector SHA-256: `{EXPOSURE_SHA256}` (checked).",
        f"- Window {WINDOW[0]} -> {WINDOW[1]}; dates read in it {res['first_date']} -> "
        f"{res['last_date']}; {res['n_days']} factor days.",
        f"- Industries: {res['n']}; dropped for a missing return: "
        f"{', '.join(res['dropped']) or 'none'}"
        + ("; null scales recomputed on the kept industries." if res["dropped"] else
           "; frozen null scales used."),
        "",
        "## Primary (D10, t_21, Holm over {H5, H5b})",
        "",
        "b in pp of annualised alpha per 1 SD of exposure; T = b / s; p from t_21; c = "
        "max(t_21 critical, empirical centred quantile).",
        "",
        "| specification | b | s | T | p (t_21) | c_0.025 | c_0.05 |",
        "|---|---|---|---|---|---|---|",
        *rows,
        "",
        *dec,
        "",
        "## Interpretive check (not part of the decision)",
        "",
        *interp,
        "",
        "## Secondary inference (never used for the decision)",
        "",
        f"- RI, permute z_delegation, H5: p = {res['ri']['h5_exposure']:.4f} (size 13.8% at "
        f"nominal 0.025 on pre-seal windows).",
        f"- RI, permute z_delegation with z_aioe in place, H5b: p = "
        f"{res['ri']['h5b_exposure']:.4f} (oversized even under exchangeability; 14.8%).",
        f"- Freedman-Lane RI, H5b: p = {res['ri']['h5b_freedman_lane']:.4f} (6.1%).",
        f"- {N_PERM:,} permutations each, one `default_rng(SEED = {SEED})` in that order.",
        f"- OLS with HC3 SEs: H5 b = {res['hc3']['h5'][0] * pp:.3f} pp (SE "
        f"{res['hc3']['h5'][1] * pp:.3f}); H5b b = {res['hc3']['h5b'][0] * pp:.3f} pp (SE "
        f"{res['hc3']['h5b'][1] * pp:.3f}).",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    res = run()
    print(res["decision"]["wording"]["H5"])
    print(res["decision"]["wording"]["H5b"])
    print(f"-> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
