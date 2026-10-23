"""H6 talk index, the AI-washing gap, divergence and the gap-return association (PAP §6, D18).

Exploratory throughout. Talk for FF49 industry j and filing year y is the share of that year's
10-K filers (distinct CIKs, `edgar.denominator`) whose 10-K is returned by EDGAR full-text search
for at least one primary term (`edgar.numerator`). T_j is talk in 2024 filings. The gap is the
standardised residual of z(T_j) on Design B `z_usage` across FF49; the gap-return association is
the §3.1 regression with gap_j in place of z_delegation, scored by `rq3.inference.vector_test`
against the same pre-seal historical null as D21, with nominal p-values in no testing family.

Defaults the PAP leaves open are fixed in PAP §11 (the Task 12 clarification).

AEI data are conversations matched to O*NET tasks; nothing here speaks to the labour market.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import polars as pl
from scipy.stats import rankdata

from aideleg.config import ROOT, SEED
from aideleg.h6 import edgar
from aideleg.results.common import WORDING, check_text, generated_line, write_csv
from aideleg.rq3 import data, inference
from aideleg.rq3.report import fmt_p, md_table, zero_assigned_bullets
from aideleg.rq3.stats import percentile_ci

__all__ = [
    "WORDING",
    "gap",
    "gap_returns",
    "pooled",
    "run_talk",
    "spearman_ci",
    "talk_table",
    "write_summary",
]

T_YEAR = 2024  # filings dated 2024-01-01 to 2024-12-31, all public before 2025-03-27
YEARS = edgar.YEARS
N_DRAWS = 10_000
LABEL = "exploratory (PAP §6, D18)"
GENERATOR = "uv run python -m aideleg.h6 talk"
SUMMARY_GENERATOR = "uv run python -m aideleg.h6 summary"
SUMMARY_HEADING = "# H6: talk vs use (exploratory, PAP §6, D18)"
TALK_HEADING = f"# H6 talk index by filing year — {LABEL}"
GAP_HEADING = f"# H6 AI-washing gap and talk–use divergence — {LABEL}"
RET_HEADING = f"# H6 gap–return association — {LABEL}; nominal p-values, in no testing family"
FIG_BY_YEAR = "fig_h6_talk_by_year"
FIG_VS_USAGE = "fig_h6_talk_vs_usage"
CONFIRMATORY_MD = ROOT / "docs/results/confirmatory_h5.md"
TALK_COLUMNS = ["year", "ff49", "ff49_short", "n_talk", "n_filers", "talk"]
GAP_COLUMNS = ["ff49_short", "T", "zT", "z_usage", "resid", "gap"]


def _ff49_names() -> pl.DataFrame:
    """`ff49, ff49_short` of the 49 Siccodes49 industries."""
    from aideleg.crosswalk.naics_ff49 import _siccodes

    return _siccodes().select("ff49", "ff49_short").unique().sort("ff49")


# --- talk ----------------------------------------------------------------------------------


def talk_table(
    num: pl.DataFrame, den: pl.DataFrame, names: pl.DataFrame | None = None
) -> pl.DataFrame:
    """`year, ff49, ff49_short, n_talk, n_filers, talk` on the denominator's grid (FF49 1..49
    and the unmapped `ff49 = null` row, whose ff49_short is null). talk = n_talk / n_filers;
    null when n_filers == 0 (listed by `null_talk`). Refuses grids that differ or a count
    above its denominator."""
    names = _ff49_names() if names is None else names
    keys = ["year", "ff49"]
    a = num.select(keys).sort(keys, nulls_last=True)
    b = den.select(keys).sort(keys, nulls_last=True)
    if not a.equals(b):
        raise ValueError("numerator and denominator grids differ")
    t = den.select(*keys, "n_filers").join(
        num.select(*keys, "n_talk"), on=keys, how="left", nulls_equal=True
    )
    if t.filter(pl.col("n_talk") > pl.col("n_filers")).height:
        raise ValueError("n_talk exceeds n_filers")
    t = t.join(names.select("ff49", "ff49_short"), on="ff49", how="left").with_columns(
        pl.when(pl.col("n_filers") > 0)
        .then(pl.col("n_talk") / pl.col("n_filers"))
        .otherwise(None)
        .cast(pl.Float64)
        .alias("talk")
    )
    return t.select(TALK_COLUMNS).sort(keys, nulls_last=True)


def null_talk(t: pl.DataFrame) -> pl.DataFrame:
    """`year, ff49_short` of the FF49 industries with no filer in a year (talk null)."""
    return (
        t.filter(pl.col("ff49").is_not_null() & pl.col("talk").is_null())
        .select("year", "ff49_short")
        .sort("year", "ff49_short")
    )


def pooled(t: pl.DataFrame) -> pl.DataFrame:
    """Per year: the pooled share over every filer, unmapped included (`talk`), the share over
    the mapped filers only (`talk_mapped`), and the unmapped count and share of filers."""
    m = pl.col("ff49").is_not_null()
    return (
        t.group_by("year")
        .agg(
            pl.col("n_talk").sum().alias("n_talk"),
            pl.col("n_filers").sum().alias("n_filers"),
            pl.col("n_talk").filter(m).sum().alias("_t_m"),
            pl.col("n_filers").filter(m).sum().alias("_f_m"),
            pl.col("n_filers").filter(~m).sum().alias("n_unmapped"),
        )
        .with_columns(
            (pl.col("n_talk") / pl.col("n_filers")).alias("talk"),
            (pl.col("_t_m") / pl.col("_f_m")).alias("talk_mapped"),
            (pl.col("n_unmapped") / pl.col("n_filers")).alias("unmapped_share"),
        )
        .select("year", "n_talk", "n_filers", "talk", "talk_mapped", "n_unmapped", "unmapped_share")
        .sort("year")
    )


def t_index(t: pl.DataFrame) -> pl.DataFrame:
    """`ff49_short, T`: talk in `T_YEAR` for the 49 FF49 industries (null row excluded)."""
    return t.filter((pl.col("year") == T_YEAR) & pl.col("ff49").is_not_null()).select(
        "ff49_short", pl.col("talk").alias("T")
    )


# --- gap and divergence --------------------------------------------------------------------


def gap(T: pl.DataFrame, expo_b: pl.DataFrame) -> pl.DataFrame:
    """`ff49_short, T, zT, z_usage, resid, gap` over the industries with T, ranked by gap
    (highest first). zT = (T - mean) / population SD; OLS of zT on [1, z_usage]; gap = resid /
    population SD(resid). z_usage is used as given (not re-standardised). Refuses an industry
    with T but no z_usage."""
    df = T.filter(pl.col("T").is_not_null()).join(
        expo_b.select("ff49_short", "z_usage"), on="ff49_short", how="left"
    )
    missing = df.filter(pl.col("z_usage").is_null())["ff49_short"].to_list()
    if missing:
        raise ValueError(f"no Design B z_usage for {missing}")
    if df.height < 3:
        raise ValueError(f"gap needs at least 3 industries with T, got {df.height}")
    t = df["T"].to_numpy().astype(float)
    sd = t.std(ddof=0)
    if sd == 0:
        raise ValueError("T has no cross-sectional variation")
    zT = (t - t.mean()) / sd
    u = df["z_usage"].to_numpy().astype(float)
    X = np.column_stack([np.ones_like(u), u])
    beta, *_ = np.linalg.lstsq(X, zT, rcond=None)
    resid = zT - X @ beta
    g = resid / resid.std(ddof=0)
    return (
        df.with_columns(pl.Series("zT", zT), pl.Series("resid", resid), pl.Series("gap", g))
        .select(GAP_COLUMNS)
        .sort(["gap", "ff49_short"], descending=[True, False])
    )


def _rank_corr(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Spearman correlation along the last axis (average ranks for ties); NaN where a row of
    `x` or `y` is constant."""
    rx = rankdata(x, axis=-1)
    ry = rankdata(y, axis=-1)
    rx = rx - rx.mean(axis=-1, keepdims=True)
    ry = ry - ry.mean(axis=-1, keepdims=True)
    sxy = (rx * ry).sum(axis=-1)
    den = np.sqrt((rx * rx).sum(axis=-1) * (ry * ry).sum(axis=-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        r = np.where(den > 0, sxy / np.where(den > 0, den, 1.0), np.nan)
    return np.clip(r, -1.0, 1.0)


def spearman_ci(x: np.ndarray, y: np.ndarray, n_draws: int = N_DRAWS, rng=None) -> dict:
    """Spearman rho of (x, y) and its 95% percentile CI from `n_draws` industry-bootstrap draws
    (pairs resampled with replacement; `default_rng(SEED)` unless `rng` is given). Draws with a
    constant x or y are undefined: dropped and counted (`n_nan`)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if x.shape != y.shape or x.ndim != 1:
        raise ValueError("x and y must be 1-d and of equal length")
    rng = np.random.default_rng(SEED) if rng is None else rng
    idx = rng.integers(0, len(x), size=(n_draws, len(x)))
    draws = _rank_corr(x[idx], y[idx])
    ok = ~np.isnan(draws)
    if not ok.any():
        raise ValueError("every bootstrap draw is undefined")
    lo, hi = percentile_ci(draws[ok])
    return {
        "rho": float(_rank_corr(x, y)),
        "ci95": (lo, hi),
        "n_nan": int((~ok).sum()),
        "n": len(x),
        "n_draws": n_draws,
    }


# --- gap-return association ----------------------------------------------------------------


def _window_alphas() -> tuple[np.ndarray, list[str]]:
    """The Design B window alphas (`confirm_h5.WINDOW`), refused unless the recomputed H5/H5b
    slopes equal the committed confirmatory record."""
    alphas, names = inference.confirmatory_alphas()
    inference.check_matches_confirmatory(
        inference.recomputed_b(alphas, names), CONFIRMATORY_MD.read_text(encoding="utf-8")
    )
    return alphas, names


def gap_returns(gap_df: pl.DataFrame) -> dict:
    """`vector_test(alphas, gap, names, control=None)` over the Design B window, industries in
    return-column order, restricted to those with a gap (the others are `no_gap`). Decimal
    units as `vector_test`; nominal p-values, in no family."""
    alphas, cols = _window_alphas()
    by = dict(zip(gap_df["ff49_short"].to_list(), gap_df["gap"].to_list(), strict=True))
    unknown = sorted(set(by) - set(cols))
    if unknown:
        raise ValueError(f"gap industries with no return column: {unknown}")
    keep = [i for i, n in enumerate(cols) if n in by]
    names = [cols[i] for i in keep]
    z = np.array([by[n] for n in names], dtype=float)
    a = np.asarray(alphas, dtype=float)[keep]
    res = dict(inference.vector_test(a, z, names, control=None))
    res["no_gap"] = [n for n in cols if n not in by]
    return res


# --- documents -----------------------------------------------------------------------------


def _f(x, fmt: str = ".3f") -> str:
    return "—" if x is None or (isinstance(x, float) and np.isnan(x)) else format(x, fmt)


ABS_SIC = 6189  # asset-backed securities issuers: in no Siccodes49 range


def composition_line(
    filers: pl.DataFrame, pool: pl.DataFrame, column: str = "the mapped-filers column"
) -> str:
    """Who the unmapped filers with a SIC are (mostly SIC 6189, asset-backed issuers) and how
    the unmapped share moves over the years, from `filers` and `pooled`; never typed."""
    per_cik = filers.select("year", "cik", "sic", "ff49").unique()
    out = per_cik.filter(pl.col("sic").is_not_null() & pl.col("ff49").is_null())
    p = pool.sort("year")
    y0, y1 = p["year"][0], p["year"][-1]
    u0, u1 = 100 * p["unmapped_share"][0], 100 * p["unmapped_share"][-1]
    trend = (
        f"The unmapped share of filers moves from {u0:.2f}% ({y0}) to {u1:.2f}% ({y1}), so "
        "part of the change in the all-filers pooled talk share is a change in the filers' "
        f"composition; {column} leaves the unmapped filers out and isolates the trend among "
        "filers assigned to an industry."
    )
    if out.height == 0:
        return f"No filer has a SIC outside Siccodes49. {trend}"
    by = (
        out.group_by("year")
        .agg(pl.len().alias("n"), (pl.col("sic") == ABS_SIC).sum().alias("n_abs"))
        .with_columns((100 * pl.col("n_abs") / pl.col("n")).alias("pct"))
    )
    n_abs = int(by["n_abs"].sum())
    return (
        f"Unmapped filers with a SIC outside Siccodes49 are mostly SIC {ABS_SIC} "
        f"(asset-backed securities issuers): {n_abs:,} of {out.height:,} filer-years over "
        f"{y0}–{y1} ({100 * n_abs / out.height:.2f}%; {by['pct'].min():.2f}% to "
        f"{by['pct'].max():.2f}% by year). {trend}"
    )


def _talk_md(
    t: pl.DataFrame,
    pool: pl.DataFrame,
    unm: pl.DataFrame,
    exh: pl.DataFrame,
    ood: pl.DataFrame,
    composition: str | None = None,
) -> str:
    rows = (
        pool.join(unm.select("year", "n_no_sic", "n_sic_outside"), on="year", how="left")
        .join(exh, on="year", how="left")
        .join(ood, on="year", how="left")
        .with_columns(pl.col("n_ood").fill_null(0))
        .sort("year")
    )
    pool_lines = [
        "| year | filers | talk filers | talk, all filers | talk, mapped filers | "
        "unmapped filers (no SIC / SIC outside Siccodes49) | unmapped share | "
        "exhibit-only talk filers | hit CIKs not in the year's filers |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows.iter_rows(named=True):
        pool_lines.append(
            f"| {r['year']} | {r['n_filers']} | {r['n_talk']} | {_f(r['talk'])} | "
            f"{_f(r['talk_mapped'])} | {r['n_unmapped']} ({r['n_no_sic']} / "
            f"{r['n_sic_outside']}) | {_f(100 * r['unmapped_share'], '.2f')}% | "
            f"{r['n_exhibit_only']} | {r['n_ood']} |"
        )
    nulls = null_talk(t)
    null_lines = [
        f"- {y}: {', '.join(nulls.filter(pl.col('year') == y)['ff49_short'])}"
        for y in sorted(set(nulls["year"].to_list()))
    ] or ["- none"]
    wide = (
        t.filter(pl.col("ff49").is_not_null())
        .pivot(on="year", index=["ff49", "ff49_short"], values="talk", sort_columns=True)
        .sort("ff49")
    )
    wide = wide.drop("ff49").rename({"ff49_short": "industry"})
    lines = [
        TALK_HEADING,
        "",
        generated_line(GENERATOR),
        "",
        "Talk for FF49 industry j and filing year y is the share of the year's 10-K filers in j "
        "whose 10-K is returned by EDGAR full-text search for at least one primary term "
        "(PAP §6 D18, §6.1 D12). It measures what filings say, not what firms do.",
        "",
        "## Definitions",
        "",
        "- Numerator: distinct CIKs among the year's filers with at least one full-text-search "
        "hit in a 10-K, 10-K405 or 10-KT (amendments excluded) filed in the year, any document "
        "of the filing (C-39, C-50). Exhibit-only talk filers are counted in it and also shown "
        "apart (C-39).",
        "- Denominator: distinct CIKs filing one of those form types in the year, from the "
        "EDGAR full index (C-49).",
        "- Industry: the CIK's current SIC (C-40) mapped to FF49 by the Siccodes49 ranges. A CIK "
        "with no SIC, or a SIC outside every range, is unmapped: it is in the denominator's "
        "`ff49 = null` row, never in an industry (C-49).",
        "- Pooled talk: total talk filers over total filers of the year, unmapped filers "
        "included; the mapped-only share is shown beside it.",
        "- Hit CIKs that are not among the year's full-index filers are listed by "
        "`edgar.out_of_denominator` and never counted (C-50).",
        "",
        "## Pooled talk by year",
        "",
        *pool_lines,
        "",
        *([composition, ""] if composition else []),
        "## FF49 industries with no filer (talk undefined)",
        "",
        *null_lines,
        "",
        "## Talk by industry and year",
        "",
        "Share of the industry's 10-K filers (— where the industry has no filer). Counts are in "
        "`talk_index.csv`, full precision, with the unmapped row.",
        "",
        md_table(wide),
        "",
        WORDING,
        "",
    ]
    return "\n".join(lines)


def _gap_md(
    g: pl.DataFrame,
    sp: dict,
    pool_t: dict,
    nulls_t: list[str],
    zero_lines: list[str],
    n_draws: int,
    counts_t: pl.DataFrame,
    composition: str | None = None,
) -> str:
    ranked = (
        g.with_row_index("rank", offset=1)
        .join(counts_t, on="ff49_short", how="left")
        .sort("rank")
        .select(
            "rank",
            pl.col("ff49_short").alias("industry"),
            pl.col("n_talk").alias(f"talk filers {T_YEAR}"),
            pl.col("n_filers").alias(f"filers {T_YEAR}"),
            "T",
            "zT",
            "z_usage",
            "gap",
        )
    )
    lo, hi = sp["ci95"]
    lines = [
        GAP_HEADING,
        "",
        generated_line(GENERATOR),
        "",
        "## Method",
        "",
        f"- T_j = talk of FF49 industry j in 10-Ks filed {T_YEAR}-01-01 → {T_YEAR}-12-31, all "
        "public before Design B's formation date, 2025-03-27 (PAP §6 D18; see "
        "`talk_index.md`).",
        f"- Industries: the FF49 industries with T ({g.height}). Industries with no {T_YEAR} "
        f"filer (T undefined): {', '.join(nulls_t) or 'none'}. Unmapped filers enter no "
        f"industry: {pool_t['n_unmapped']} of {pool_t['n_filers']} {T_YEAR} filers "
        f"({100 * pool_t['unmapped_share']:.2f}%).",
        *([f"- {composition}"] if composition else []),
        "- z_usage: Design B (release r2) `z_usage`, conversations matched to O*NET tasks "
        "aggregated to FF49 (PAP §2.1), from the hash-checked `rq3.data.exposures()`; used as "
        "given, not re-standardised over the industries with T.",
        "- zT = (T − mean) / population SD across those industries; OLS of zT on [1, z_usage]; "
        "gap_j = the residual divided by its population SD. gap_j > 0: the industry's talk is "
        "higher than its z_usage predicts in this cross-section.",
        f"- Divergence: Spearman(T, z_usage), average ranks for ties, with a 95% percentile CI "
        f"from {n_draws:,} industry-bootstrap draws (industries resampled with replacement as "
        "(T, z_usage) pairs, `default_rng(SEED)`); draws with a constant T or z_usage are "
        "undefined, dropped and counted.",
        *zero_lines,
        "",
        "## Divergence: Spearman(T, z_usage)",
        "",
        "| rho | 95% CI | industries | bootstrap draws | undefined draws |",
        "|---|---|---|---|---|",
        f"| {sp['rho']:.3f} | [{lo:.3f}, {hi:.3f}] | {sp['n']} | {sp['n_draws']} | {sp['n_nan']} |",
        "",
        "## Ranking of the AI-washing gap (highest first)",
        "",
        "T is a share of filers; zT, z_usage and gap are in SD units. Full precision, with the "
        "residual before scaling, in `gap.csv`.",
        "",
        md_table(ranked),
        "",
        WORDING,
        "",
    ]
    return "\n".join(lines)


def _ret_md(res: dict, zero_lines: list[str]) -> str:
    from aideleg import confirm_h5, power

    lo, hi = res["ci_0.05"]
    w0, w1 = confirm_h5.WINDOW
    pp = 100.0
    table = [
        "| statistic | value |",
        "|---|---|",
        f"| b (pp of annualised alpha per 1 SD of gap) | {res['b'] * pp:.3f} |",
        f"| s (pp) | {res['s'] * pp:.3f} |",
        f"| b̄ (pp) | {res['bbar'] * pp:.3f} |",
        f"| q_0.975 (empirical centred quantile) | {res['q_0.975']:.3f} |",
        f"| critical, max(t_{power.T_DF}, q) | {res['crit_0.05']:.3f} |",
        f"| T, H0: b = b̄ (D21, primary null) | {res['T_bbar']:.3f} |",
        f"| p, H0: b = b̄ (nominal) | {fmt_p(res['p_bbar'])} |",
        f"| T, H0: b = 0 (secondary null) | {res['T_zero']:.3f} |",
        f"| p, H0: b = 0 (nominal) | {fmt_p(res['p_zero'])} |",
        f"| 95% CI for b, b ± critical × s (pp) | [{lo * pp:.3f}, {hi * pp:.3f}] |",
        f"| industries | {res['n']} |",
    ]
    lines = [
        RET_HEADING,
        "",
        generated_line(GENERATOR),
        "",
        "The §3.1 regression with gap_j in place of z_delegation (PAP §6 D18, C-42). It is "
        "exploratory: its p-values are nominal, it belongs to no testing family, and it does "
        "not revisit the H5/H5b decision recorded in `docs/results/confirmatory_h5.md`.",
        "",
        "## Specification",
        "",
        f"- Alphas: `aideleg.power.window_alphas` over {w0} → {w1} (the Design B window; FF49 "
        "daily value-weighted, FF5 + UMD, annualised), recomputed through the guarded loaders; "
        "the H5/H5b slopes they give equal the committed record (checked).",
        "- Regression: alpha_j = a + b · gap_j + e_j, OLS, unweighted, no control (the H5 form, "
        "C-42); gap_j from `gap.md`, not re-standardised after drops.",
        "- Inference as §3.3 (`rq3.inference.vector_test`): s, b̄ and q recomputed for the gap "
        f"vector on the same pre-seal historical windows; critical = max(t_{power.T_DF}, q); "
        "primary null "
        "b = b̄ (D21), b = 0 secondary; the CI is b ± critical × s.",
        f"- Industries without a gap (no {T_YEAR} filer): {', '.join(res['no_gap']) or 'none'}. "
        f"Dropped for a missing return in the window: {', '.join(res['dropped']) or 'none'}.",
        *zero_lines,
        "",
        "## Result",
        "",
        *table,
        "",
        WORDING,
        "",
    ]
    return "\n".join(lines)


def _fig_by_year(t: pl.DataFrame, pool: pl.DataFrame):
    import matplotlib.pyplot as plt

    from aideleg.figures import FIGSIZE, PALETTE, apply_style

    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["double"])
    ind = t.filter(pl.col("ff49").is_not_null())
    for name in sorted(set(ind["ff49_short"].to_list())):
        s = ind.filter((pl.col("ff49_short") == name) & pl.col("talk").is_not_null()).sort("year")
        ax.plot(s["year"].to_list(), s["talk"].to_list(), color="#bbbbbb", lw=0.5)
    ax.plot(
        pool["year"].to_list(),
        pool["talk"].to_list(),
        color=PALETTE[0],
        lw=1.6,
        marker="o",
        ms=3,
        label="pooled, all filers",
    )
    ax.plot([], [], color="#bbbbbb", lw=0.5, label="one FF49 industry")
    ax.set_xlabel("filing year")
    ax.set_ylabel("share of 10-K filers with a primary AI term")
    ax.set_title("H6 talk index by filing year (exploratory)")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def _fig_vs_usage(g: pl.DataFrame):
    import matplotlib.pyplot as plt

    from aideleg.figures import FIGSIZE, PALETTE, apply_style

    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["double"])
    x, y = g["z_usage"].to_numpy(), g["T"].to_numpy()
    ax.scatter(x, y, s=12, color=PALETTE[0], zorder=3)
    ax.set_xlabel("Design B z_usage (SD units)")
    ax.set_ylabel(f"T: share of {T_YEAR} 10-K filers with a primary AI term")
    ax.set_title(f"H6 {T_YEAR} talk vs Design B z_usage across FF49 (exploratory)")
    fig.tight_layout()
    _place_labels(fig, ax, g["ff49_short"].to_list(), x, y)
    return fig


def _place_labels(fig, ax, names: list[str], x: np.ndarray, y: np.ndarray) -> None:
    """Deterministic greedy label placement: each label (in order of y, then name) takes the
    first candidate offset whose box overlaps no placed label and no marker; labels away from
    their point get a thin leader line. Presentation only."""
    from matplotlib.transforms import Bbox

    renderer = fig.canvas.get_renderer()
    pts = ax.transData.transform(np.column_stack([x, y]))
    scale = fig.dpi / 72.0
    marker = 3.0 * scale
    markers = [
        Bbox.from_extents(px - marker, py - marker, px + marker, py + marker) for px, py in pts
    ]
    dirs = [(1, 1), (1, -1), (-1, 1), (-1, -1), (1, 0), (-1, 0), (0, 1), (0, -1)]
    cands = [(dx * r, dy * r) for r in (3, 8, 13, 18, 24, 30, 38, 46) for dx, dy in dirs]
    placed: list = []
    order = sorted(range(len(names)), key=lambda i: (y[i], names[i]))
    for i in order:
        probe = ax.text(0, 0, names[i], fontsize=5)
        ext = probe.get_window_extent(renderer)
        probe.remove()
        w, h = ext.width, ext.height
        chosen = cands[-1]
        for dx, dy in cands:
            cx = pts[i][0] + dx * scale
            cy = pts[i][1] + dy * scale
            x0 = cx if dx >= 0 else cx - w
            x0 = x0 - w / 2 if dx == 0 else x0
            y0 = cy if dy >= 0 else cy - h
            y0 = y0 - h / 2 if dy == 0 else y0
            box = Bbox.from_bounds(x0, y0, w, h)
            others = markers[:i] + markers[i + 1 :]
            if not any(box.overlaps(b) for b in placed + others):
                chosen = (dx, dy)
                placed.append(box)
                break
        dx, dy = chosen
        ha = "center" if dx == 0 else ("left" if dx > 0 else "right")
        va = "center" if dy == 0 else ("bottom" if dy > 0 else "top")
        far = max(abs(dx), abs(dy)) > 3
        ax.annotate(
            names[i],
            (x[i], y[i]),
            xytext=(dx, dy),
            textcoords="offset points",
            fontsize=5,
            ha=ha,
            va=va,
            arrowprops={
                "arrowstyle": "-",
                "lw": 0.3,
                "color": "#888888",
                "shrinkA": 0,
                "shrinkB": 2,
            }
            if far
            else None,
        )


def run_talk(
    out_dir: Path,
    *,
    filers: pl.DataFrame | None = None,
    hits: pl.DataFrame | None = None,
    fig_dir: Path | None = None,
    n_draws: int = N_DRAWS,
) -> dict:
    """Write `talk_index.{md,csv}`, `gap.{md,csv}` and `gap_returns.md` to `out_dir`, and the
    two figures to `fig_dir` when one is given. `filers` and `hits` default to the derived
    parquets. Returns the pooled series, the gap frame, Spearman and the gap-return result."""
    out_dir = Path(out_dir)
    filers = pl.read_parquet(edgar.FILERS) if filers is None else filers
    hits = pl.read_parquet(edgar.FTS_HITS) if hits is None else hits
    den = edgar.denominator(filers)
    num = edgar.numerator(hits, filers)
    t = talk_table(num, den)
    pool = pooled(t)
    exh = num.group_by("year").agg(pl.col("n_exhibit_only").sum())
    ood = (
        edgar.out_of_denominator(hits, filers)
        .group_by("year")
        .agg(pl.len().cast(pl.Int64).alias("n_ood"))
    )
    comp = composition_line(filers, pool)
    talk_text = _talk_md(t, pool, edgar.unmapped_report(filers), exh, ood, comp)
    check_text(talk_text)

    expo_b = data.exposures().filter(pl.col("design") == "B").select("ff49_short", "z_usage")
    zero_lines = zero_assigned_bullets(["B"], data.zero_assigned())
    g = gap(t_index(t), expo_b)
    sp = spearman_ci(g["T"].to_numpy(), g["z_usage"].to_numpy(), n_draws=n_draws)
    pool_t = pool.filter(pl.col("year") == T_YEAR).row(0, named=True)
    nulls_t = null_talk(t).filter(pl.col("year") == T_YEAR)["ff49_short"].to_list()
    counts_t = t.filter((pl.col("year") == T_YEAR) & pl.col("ff49").is_not_null()).select(
        "ff49_short", "n_talk", "n_filers"
    )
    comp_gap = composition_line(filers, pool, "the mapped-filers column of `talk_index.md`")
    gap_text = _gap_md(g, sp, pool_t, nulls_t, zero_lines, n_draws, counts_t, comp_gap)
    check_text(gap_text)
    res = gap_returns(g)
    ret_text = _ret_md(res, zero_lines)
    check_text(ret_text)

    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(t, out_dir / "talk_index.csv")
    write_csv(g, out_dir / "gap.csv")
    (out_dir / "talk_index.md").write_text(talk_text, encoding="utf-8")
    (out_dir / "gap.md").write_text(gap_text, encoding="utf-8")
    (out_dir / "gap_returns.md").write_text(ret_text, encoding="utf-8")
    if fig_dir is not None:
        from aideleg.figures import save_figure

        save_figure(_fig_by_year(t, pool), FIG_BY_YEAR, out_dir=Path(fig_dir))
        save_figure(_fig_vs_usage(g), FIG_VS_USAGE, out_dir=Path(fig_dir))
    return {"pooled": pool, "gap": g, "spearman": sp, "gap_returns": res, "null_T": nulls_t}


def _title(path: Path) -> str:
    first = path.read_text(encoding="utf-8").splitlines()[0]
    if not first.startswith("# "):
        raise ValueError(f"{path.name} does not start with a heading")
    return first[2:]


def write_summary(out_dir: Path) -> Path:
    """Write `out_dir/summary.md`: the heading, the exploratory status and a link to every
    other doc in `out_dir`, with no estimate."""
    out_dir = Path(out_dir)
    docs = sorted(p for p in out_dir.glob("*.md") if p.name != "summary.md")
    lines = [
        SUMMARY_HEADING,
        "",
        generated_line(SUMMARY_GENERATOR),
        "",
        "H6 is exploratory (PAP §6 D18): no H6 output is a confirmatory test. The gap–return "
        "association reports nominal p-values and belongs to no testing family; it does not "
        "revisit the H5/H5b decision. Each document states its own estimates, intervals and "
        "nominal p-values; none is repeated here.",
        "",
        "## Documents",
        "",
        *[f"- [{p.name}]({p.name}): {_title(p)}" for p in docs],
        "",
        WORDING,
        "",
    ]
    text = "\n".join(lines)
    check_text(text)
    path = out_dir / "summary.md"
    path.write_text(text, encoding="utf-8")
    return path
