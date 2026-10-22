"""RQ2 descriptives: what Claude users are matched to against what exposure benchmarks say.

AEI data are conversations matched to O*NET tasks. RQ2 is descriptive: there is no hypothesis test
and no decision here. The one inferential-looking quantity, a Spearman correlation across the 49
industries, carries an industry bootstrap percentile interval as a description of its spread.

Rank convention: rank 1 is the highest value. `rank_gap = rank_does - rank_could`, so a positive
gap means an industry sits lower on the AEI measure (`does`) than on the benchmark (`could`).
The Eloundou human beta (`z_eloundou`) is the headline benchmark; the GPT-4 beta sits beside it
(D8).
"""

import numpy as np
import polars as pl
from scipy.stats import rankdata

from aideleg.config import SEED

AEI_COLS = ("z_usage", "z_delegation", "z_augmentation")
BENCH_COLS = ("z_aioe", "z_eloundou", "z_eloundou_gpt4")
SPEARMAN_COLUMNS = ["aei", "benchmark", "n", "spearman", "ci_low", "ci_high", "n_draws_used"]


def bootstrap_indices(n: int, designs: tuple[str, ...] = ("B", "A_pooled"),
                      draws: int = 10_000) -> dict[str, np.ndarray]:
    """One (draws, n) industry-resample matrix per design, from one seeded generator in order."""
    rng = np.random.default_rng(SEED)
    return {d: rng.integers(0, n, size=(draws, n)) for d in designs}


def _spearman_rows(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Spearman rho per row: average-tie ranks, then Pearson. NaN where a row is constant."""
    rx, ry = rankdata(x, axis=-1), rankdata(y, axis=-1)
    rx = rx - rx.mean(axis=-1, keepdims=True)
    ry = ry - ry.mean(axis=-1, keepdims=True)
    num = (rx * ry).sum(axis=-1)
    den = np.sqrt((rx * rx).sum(axis=-1) * (ry * ry).sum(axis=-1))
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 0, num / den, np.nan)


def spearman_bootstrap(df: pl.DataFrame, pairs: list[tuple[str, str]],
                       idx: np.ndarray) -> pl.DataFrame:
    """Spearman rho per (aei, benchmark) pair with a 2.5/97.5 percentile industry-bootstrap CI.

    `idx` is a (B, n) resample matrix with n = `df.height`. A draw in which either vector is
    constant has no rho; it is excluded and `n_draws_used` counts the draws kept.
    """
    if idx.shape[1] != df.height:
        raise ValueError(f"idx has n={idx.shape[1]} but the frame has {df.height} rows")
    rows = []
    for aei, bench in pairs:
        x, y = df[aei].to_numpy().astype(float), df[bench].to_numpy().astype(float)
        point = float(_spearman_rows(x, y))
        draws = _spearman_rows(x[idx], y[idx])
        draws = draws[~np.isnan(draws)]
        lo, hi = np.percentile(draws, [2.5, 97.5]) if draws.size else (np.nan, np.nan)
        rows.append({"aei": aei, "benchmark": bench, "n": df.height, "spearman": point,
                     "ci_low": float(lo), "ci_high": float(hi), "n_draws_used": int(draws.size)})
    return pl.DataFrame(rows, schema={"aei": pl.String, "benchmark": pl.String, "n": pl.Int64,
                                      "spearman": pl.Float64, "ci_low": pl.Float64,
                                      "ci_high": pl.Float64, "n_draws_used": pl.Int64})


def _joined(exposure: pl.DataFrame, bench: pl.DataFrame) -> pl.DataFrame:
    cols = [c for c in BENCH_COLS if c in bench.columns and c not in exposure.columns]
    return exposure.join(bench.select("ff49", *cols), on="ff49", how="left")


def top_bottom(exposure: pl.DataFrame, bench: pl.DataFrame, col: str, k: int = 10) -> pl.DataFrame:
    """The k highest and k lowest industries on `col`, with the three benchmarks beside them.

    `rank` counts from the highest (1); the bottom block therefore carries ranks n-k+1 .. n.
    """
    d = (_joined(exposure, bench).sort([col, "ff49_short"], descending=[True, False])
         .with_row_index("rank", offset=1))
    n = d.height
    d = d.with_columns(side=pl.when(pl.col("rank") <= k).then(pl.lit("top"))
                       .when(pl.col("rank") > n - k).then(pl.lit("bottom")))
    cols = ["rank", "side", "ff49_short", col]
    cols += [c for c in ("z_aioe", "z_eloundou", "z_eloundou_gpt4") if c != col]
    cols.append("emp_covered_share")
    return d.filter(pl.col("side").is_not_null()).select(cols).with_columns(
        pl.col("rank").cast(pl.Int64))


def rank_gaps(exposure: pl.DataFrame, bench: pl.DataFrame, aei: str = "z_delegation",
              bench_col: str = "z_aioe", k: int = 10) -> pl.DataFrame:
    """Rank on the AEI measure minus rank on the benchmark; the k largest and k smallest gaps.

    Rank 1 is the highest value; ties break on the industry name. Output is sorted by gap,
    largest first, and holds each industry once.
    """
    d = _joined(exposure, bench)
    does = d.sort([aei, "ff49_short"], descending=[True, False]).with_row_index("rank_does", 1)
    could = d.sort([bench_col, "ff49_short"], descending=[True, False]).with_row_index(
        "rank_could", 1)
    g = (does.select("ff49_short", "rank_does")
         .join(could.select("ff49_short", "rank_could"), on="ff49_short")
         .with_columns(pl.col("rank_does").cast(pl.Int64), pl.col("rank_could").cast(pl.Int64))
         .with_columns(gap=pl.col("rank_does") - pl.col("rank_could"))
         .sort(["gap", "ff49_short"], descending=[True, False]))
    if g.height <= 2 * k:
        return g
    return pl.concat([g.head(k), g.tail(k)])


def _wquantile(values: np.ndarray, weights: np.ndarray, q: float) -> float:
    order = np.argsort(values, kind="stable")
    v, w = values[order], weights[order]
    cum = np.cumsum(w)
    return float(v[np.searchsorted(cum, q * cum[-1], side="left")])


def bound_widths(exposure: pl.DataFrame,
                 occ_exposure: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Design B bound widths: per industry, and usage-weighted quantiles across occupations."""
    ff = (exposure.select("ff49_short", "E_delegation", "E_delegation_lb", "E_delegation_ub")
          .with_columns(width=pl.col("E_delegation_ub") - pl.col("E_delegation_lb"))
          .with_columns(width_pct_of_E=100 * pl.col("width") / pl.col("E_delegation")))
    rows = []
    for name, lb, ub in (("automation_share_all", "automation_share_all_lb",
                          "automation_share_all_ub"), ("D", "D_lb", "D_ub")):
        o = occ_exposure.select("usage_share", lb, ub).drop_nulls()
        w = (o[ub] - o[lb]).to_numpy()
        wt = o["usage_share"].to_numpy()
        keep = wt > 0
        rows.append({"measure": f"{name}_ub - {name}_lb", "n_occupations": int(keep.sum()),
                     "p25": _wquantile(w[keep], wt[keep], 0.25),
                     "p50": _wquantile(w[keep], wt[keep], 0.5),
                     "p75": _wquantile(w[keep], wt[keep], 0.75)})
    return ff, pl.DataFrame(rows)
