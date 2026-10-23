"""Recomputed confirmatory alphas, the historical-null vector test, and the Softw influence
diagnostics the PAP assigns to the period after the confirmatory run (§3.3, P11).

- `confirmatory_alphas` reruns the frozen `power.window_alphas` over `confirm_h5.WINDOW` on
  market data read through the guarded loaders; the slopes it gives must equal the committed
  record (`check_matches_confirmatory`), or the run refuses.
- `vector_test` scores any vector of industry alphas against the same pre-seal historical null
  as the confirmatory test (s, bbar, empirical quantile, t_21), nominal and single-test.
- `influence` gives DFBETAS on the exposure coefficient, Cook's D and leverage per industry for
  H5 and H5b. These are post-result secondary diagnostics; they do not change the confirmatory
  decision.

AEI data are conversations matched to O*NET tasks; nothing here speaks to the labour market.
"""

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.api as sm
from scipy import stats as _st
from statsmodels.stats.outliers_influence import OLSInfluence

from aideleg import confirm_h5, power
from aideleg.config import DERIVED, ROOT
from aideleg.results.common import WORDING, check_text, generated_line, write_csv
from aideleg.rq3 import data

CONFIRMATORY_MD = ROOT / "docs/results/confirmatory_h5.md"
GENERATOR = "uv run python -m aideleg.rq3 influence"
HEADING = ("# Influence diagnostics for the confirmatory H5/H5b fits (PAP §3.3, P11) — not part "
           "of the decision")
SPECS = ("H5", "H5b")
TOP_K = 5
_KEYS = {"H5": "h5", "H5b": "h5b"}


def confirmatory_alphas() -> tuple[np.ndarray, list[str]]:
    """Annualised decimal FF5+UMD alphas over `confirm_h5.WINDOW`, one per return column (NaN
    where `power.window_alphas` gives null), and the column names in the same order."""
    returns, factors = data.daily("VW")
    names = [c for c in returns.columns if c != "date"]
    a = power.window_alphas(returns, factors, *confirm_h5.WINDOW).to_numpy().astype(float)
    return a, names


def _cache_path() -> Path:
    return DERIVED / "rq3/historical_alphas.npz"


def _fingerprint(windows: list, returns: pl.DataFrame, factors: pl.DataFrame,
                 names: list[str]) -> str:
    """SHA-256 of the inputs the historical matrix depends on: the window count and first and
    last window dates, the shape and date span of the pre-seal return and factor frames, and
    `names`."""
    def frame(df: pl.DataFrame) -> list:
        return [list(df.shape), str(df["date"].min()), str(df["date"].max())]

    key = {"windows": [len(windows), str(windows[0][0]), str(windows[-1][1])],
           "returns": frame(returns), "factors": frame(factors), "names": list(names)}
    return hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()


def historical_alphas(names: list[str]) -> np.ndarray:
    """The 378 x len(names) pre-seal alpha matrix (power.historical_windows), columns as
    `names`. Cached with an input fingerprint (`_fingerprint`); recomputed when it differs."""
    path = _cache_path()
    windows = power.historical_windows()
    returns, factors = power._load_returns()
    fp = _fingerprint(windows, returns, factors, names)
    if path.is_file():
        with np.load(path, allow_pickle=False) as f:
            if "fingerprint" in f and str(f["fingerprint"]) == fp \
                    and f["names"].tolist() == list(names):
                return f["alphas"]
    A = power._alpha_matrix(windows, returns, factors, list(names))
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, alphas=A, names=np.array(list(names), dtype=str), fingerprint=np.array(fp))
    return A


def _p_t(T: float) -> float:
    return float(2 * _st.t.sf(abs(T), power.T_DF))


def vector_test(alphas: np.ndarray, z: np.ndarray, names: list[str],
                control: np.ndarray | None = None, hist: np.ndarray | None = None) -> dict:
    """Slope of `alphas` on [1, z(, control)] scored against the historical null (decimal).

    Industries with a NaN alpha are dropped (z not re-standardised). The historical slopes use
    the kept columns of `hist` (default `historical_alphas(kept)`); s = their sd (ddof = 1),
    bbar = their mean, q = the empirical centred 0.975 quantile, crit_0.05 = max(t_21, q).
    Both D21 nulls (b = bbar and b = 0) with p from t_21; ci_0.05 = b +- crit_0.05 * s.
    Nominal and single-test: no Holm step."""
    alphas = np.asarray(alphas, dtype=float)
    z = np.asarray(z, dtype=float)
    lens = {"alphas": len(alphas), "z": len(z), "names": len(names)}
    if control is not None:
        lens["control"] = len(control)
    if hist is not None:
        lens["hist columns"] = np.asarray(hist).shape[1]
    if len(set(lens.values())) != 1:
        raise ValueError(f"vector_test: lengths differ: {lens}")
    ok = ~np.isnan(alphas)
    kept = [n for n, k in zip(names, ok, strict=True) if k]
    dropped = [n for n, k in zip(names, ok, strict=True) if not k]
    zk = z[ok]
    ck = None if control is None else np.asarray(control, dtype=float)[ok]
    hk = historical_alphas(kept) if hist is None else np.asarray(hist, dtype=float)[:, ok]
    b = float(power.ols_weights(zk, ck) @ alphas[ok])
    slopes = power.slope_null_distribution(zk, [None] * len(hk), alphas=hk, control=ck)
    s = float(np.std(slopes, ddof=1))
    bbar = float(np.mean(slopes))
    q = power.own_size(slopes, {})["q_0.975"]
    crit = max(power.t_crit(0.05), q)
    T_bbar, T_zero = (b - bbar) / s, b / s
    return {"b": b, "s": s, "bbar": bbar, "q_0.975": q, "crit_0.05": crit,
            "T_bbar": T_bbar, "p_bbar": _p_t(T_bbar), "T_zero": T_zero, "p_zero": _p_t(T_zero),
            "ci_0.05": (b - crit * s, b + crit * s), "n": len(kept), "dropped": dropped}


def influence(alphas: np.ndarray, z: np.ndarray, c: np.ndarray, names: list[str]
              ) -> pl.DataFrame:
    """Per industry with an alpha: DFBETAS of the exposure coefficient, Cook's D and leverage,
    for H5 ([1, z]) and H5b ([1, z, c])."""
    alphas = np.asarray(alphas, dtype=float)
    ok = ~np.isnan(alphas)
    kept = [n for n, k in zip(names, ok, strict=True) if k]
    a, zk, ck = alphas[ok], np.asarray(z, dtype=float)[ok], np.asarray(c, dtype=float)[ok]
    frames = []
    for spec, X in (("H5", power._design(zk)), ("H5b", power._design(zk, ck))):
        inf = OLSInfluence(sm.OLS(a, X).fit())
        frames.append(pl.DataFrame({
            "spec": [spec] * len(kept), "ff49_short": kept,
            "dfbetas_b": inf.dfbetas[:, 1], "cooks_d": inf.cooks_distance[0],
            "leverage": inf.hat_matrix_diag}))
    return pl.concat(frames)


def check_matches_confirmatory(b: dict[str, float], text: str) -> None:
    """Raise ValueError unless round(b * 100, 3) equals the b printed in the committed record's
    `| H5 | <b> |` and `| H5b | <b> |` rows."""
    for label, key in _KEYS.items():
        m = re.search(rf"^\| {re.escape(label)} \| (-?\d+\.\d+) \|", text, flags=re.M)
        if m is None:
            raise ValueError(f"no `| {label} | <b> |` row in the confirmatory record")
        printed = float(m.group(1))
        got = round(b[key] * 100, 3)
        if got != printed:
            raise ValueError(f"{label}: recomputed b = {got:.3f} pp, committed record prints "
                             f"{m.group(1)} pp; the recomputation differs from the record")


def _exposure_b(names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """Design B `z_delegation` and `z_aioe`, ordered as `names` (hash-checked by data)."""
    ex = data.exposures().filter(pl.col("design") == "B")
    by = {r["ff49_short"]: (r["z_delegation"], r["z_aioe"]) for r in ex.iter_rows(named=True)}
    if sorted(by) != sorted(names):
        raise ValueError("Design B exposure industries do not match the FF49 return columns")
    z = np.array([by[n][0] for n in names], dtype=float)
    c = np.array([by[n][1] for n in names], dtype=float)
    return z, c


def recomputed_b(alphas: np.ndarray, names: list[str]) -> dict[str, float]:
    """b for H5 and H5b on the industries with an alpha, as `confirm_h5` computes them."""
    z, c = _exposure_b(names)
    ok = ~np.isnan(alphas)
    return {"h5": float(power.ols_weights(z[ok]) @ alphas[ok]),
            "h5b": float(power.ols_weights(z[ok], c[ok]) @ alphas[ok])}


def _fmt(x: float) -> str:
    return f"{x:.4f}"


def _report(df: pl.DataFrame, b: dict[str, float], dropped: list[str], zero_pct: float) -> str:
    softw = [f"| {spec} | {_fmt(r['dfbetas_b'])} | {_fmt(r['cooks_d'])} | {_fmt(r['leverage'])} |"
             for spec in SPECS
             for r in df.filter((pl.col("spec") == spec) & (pl.col("ff49_short") == power.SOFTW)
                                ).iter_rows(named=True)]
    top = []
    for spec in SPECS:
        sub = df.filter(pl.col("spec") == spec).sort(["cooks_d", "ff49_short"],
                                                     descending=[True, False]).head(TOP_K)
        top += [f"| {spec} | {i} | {r['ff49_short']} | {_fmt(r['cooks_d'])} | "
                f"{_fmt(r['dfbetas_b'])} | {_fmt(r['leverage'])} |"
                for i, r in enumerate(sub.iter_rows(named=True), start=1)]
    n = df.filter(pl.col("spec") == "H5").height
    lines = [
        HEADING,
        "",
        generated_line(GENERATOR),
        "",
        "Post-result secondary diagnostics that PAP §3.3 (P11) assigns to the period after the "
        "confirmatory run. They describe how much single industries move the committed H5 and "
        "H5b slopes; the confirmatory decision in `docs/results/confirmatory_h5.md` stands as "
        "recorded and is not reinterpreted here.",
        "",
        "## Inputs",
        "",
        f"- Alphas: `aideleg.power.window_alphas` over {confirm_h5.WINDOW[0]} -> "
        f"{confirm_h5.WINDOW[1]} (FF49 daily value-weighted, FF5 + UMD), read through the "
        f"guarded loaders. Industries: {n}; dropped for a missing return: "
        f"{', '.join(dropped) or 'none'}.",
        f"- Recomputed b: H5 {b['h5'] * 100:.3f} pp, H5b {b['h5b'] * 100:.3f} pp per 1 SD of "
        "exposure; equal to the committed record at three decimals (checked).",
        "- Fits: OLS of alpha on [1, z_delegation] (H5) and [1, z_delegation, z_aioe] (H5b), "
        "Design B exposure. DFBETAS on the z_delegation coefficient, Cook's D and leverage from "
        "`statsmodels` `OLSInfluence`. All three are unitless.",
        f"- Zero-assigned employment share, Design B: {zero_pct:.2f}% (D3)",
        "",
        "## Softw",
        "",
        "| specification | DFBETAS on b | Cook's D | leverage |",
        "|---|---|---|---|",
        *softw,
        "",
        f"## The {TOP_K} largest Cook's D per specification",
        "",
        "| specification | rank | industry | Cook's D | DFBETAS on b | leverage |",
        "|---|---|---|---|---|---|",
        *top,
        "",
        "Every industry's values are in `influence.csv` (full precision).",
        "",
        WORDING,
        "",
    ]
    return "\n".join(lines)


def main_influence(out_dir: Path) -> pl.DataFrame:
    """Recompute the confirmatory alphas, refuse unless b matches the committed record, then
    write `influence.csv` and `influence.md` to `out_dir`."""
    out_dir = Path(out_dir)
    alphas, names = confirmatory_alphas()
    b = recomputed_b(alphas, names)
    check_matches_confirmatory(b, CONFIRMATORY_MD.read_text(encoding="utf-8"))
    z, c = _exposure_b(names)
    df = influence(alphas, z, c, names)
    dropped = [n for n, a in zip(names, alphas, strict=True) if np.isnan(a)]
    za = data.zero_assigned().filter(pl.col("design") == "B")
    if za.height != 1:
        raise ValueError("no zero-assigned share for Design B")
    text = _report(df, b, dropped, float(za["no_usage_emp_pct"][0]))
    check_text(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(df, out_dir / "influence.csv")
    (out_dir / "influence.md").write_text(text, encoding="utf-8")
    return df
