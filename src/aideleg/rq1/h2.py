"""H2: measured within-task automation across releases (PAP §4.2, §5, D2, D22).

AEI data are conversations matched to O*NET tasks. A row is one (task, release) value of the
conversations matched to that task. β is the change in the *measured* within-task outcome per
year. It includes any change in the classifier and in platform scope, which no release names.

Rules
- **Panel** (`build_h2_panel`). Global `onet_task` rows of `source`, `unmatched:*` excluded.
  Each release is reduced to one row per task by `two_month_mean` (D13; it matters only for
  r6, which has two months). `balanced=True` keeps tasks with a non-null outcome in every
  listed release (the primary, D2). `balanced=False` keeps every non-null (task, release) row
  of tasks with such rows in at least two releases (R22 only; never the confirmatory H2).
  `weight` is the task's mean D13 `pct` over the listed releases, unpublished = 0, so weights
  do not move with release.
- **Time.** t_r in years since r2: midpoints of the release's `claude_ai` window (primary) or
  publication dates (R36).
- **Primary** (`estimate_h2`). The exact PAP §4.2 statsmodels call: WLS of the outcome on
  [t, all task dummies (+ an r6 dummy)], no constant, task-clustered CRV1, t with G_task - 1
  df. `p_family` = its two-sided p of the trend.
- **Fast path** (`clustered_within`). The same β and covariance from the weighted within-task
  transformation; it serves the wild bootstrap, the release-label randomisation and the
  release effects, and is cross-checked against the statsmodels fit on every call.
- **Wild bootstrap** (D22 item 3). Clusters = releases; restricted model = task FE (+ r6
  dummy); every Webb vector in WEBB^R is enumerated (no random draws);
  p = #{|t*| ≥ |t|} / 6^R.
- **Release-label randomisation** (D22 item 4). Every permutation of the R time values over the
  R releases, identity included; descriptive only.
- **Release effects.** The same WLS with release dummies (base r2) in place of t.
- Ties in |t*| ≥ |t| are counted with a relative tolerance of `TIE_RTOL`, so the identity
  draw (Webb vector of ones, identity ordering) always counts despite rounding.
"""

import itertools
import math
from typing import Literal

import numpy as np
import polars as pl
import scipy.sparse as sp
import statsmodels.api as sm

from aideleg.config import RELEASES
from aideleg.rq1.inputs import two_month_mean
from aideleg.rq1.result import Coef, HypothesisResult
from aideleg.rq1.twoway import _t_coef

H2_RELEASES = ("r2", "r3", "r4", "r5")
WEBB = (-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0, math.sqrt(1.5))
ALPHA_H2 = 0.0125
TIE_RTOL = 1e-9
STATSMODELS_RTOL = 1e-8  # fast path vs the exact call
_DRAW_CELLS = 4_000_000  # rows x draws per bootstrap chunk
_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def _ordered(releases) -> list[str]:
    return sorted(set(releases), key=lambda r: RELEASES[r])


def release_times(panel: pl.DataFrame, releases,
                  basis: Literal["midpoint", "publication"] = "midpoint") -> dict[str, float]:
    """t_r in years (365.25 days) since r2, for each listed release.

    midpoint: mid = min(period_start) + (max(period_end) - min(period_start)) / 2 over the
    release's `claude_ai` periods. publication: `RELEASES[r]`.
    """
    if basis == "publication":
        return {r: (RELEASES[r] - RELEASES["r2"]).days / 365.25 for r in releases}
    if basis != "midpoint":
        raise ValueError(f"unknown time basis {basis!r}")

    def mid(r: str) -> float:
        p = panel.filter((pl.col("release") == r) & (pl.col("source") == "claude_ai"))
        if p.is_empty():
            raise ValueError(f"no claude_ai periods for {r}")
        start, end = p["period_start"].min(), p["period_end"].max()
        return start.toordinal() + (end.toordinal() - start.toordinal()) / 2

    ref = mid("r2")
    return {r: (mid(r) - ref) / 365.25 for r in releases}


def build_h2_panel(panel: pl.DataFrame, *, releases=H2_RELEASES, source: str = "claude_ai",
                   outcome: str = "automation_pct", balanced: bool = True,
                   time_basis: Literal["midpoint", "publication"] = "midpoint"
                   ) -> pl.DataFrame:
    """`task_node, release, t, <outcome>, weight`, one row per kept (task, release)."""
    releases = tuple(releases)
    if len(set(releases)) != len(releases) or len(releases) < 2:
        raise ValueError(f"releases must be at least two distinct IDs, got {releases}")
    times = release_times(panel, releases, time_basis)
    parts = []
    for r in releases:
        rel = panel.filter((pl.col("release") == r) & (pl.col("source") == source))
        long = rel.filter((pl.col("geo_level") == "global") & (pl.col("taxonomy") == "onet_task")
                          & pl.col("metric").is_in(["pct", outcome])
                          & ~pl.col("node_id").str.starts_with("unmatched:"))
        if long.is_empty():
            raise ValueError(f"no global onet_task rows for {r}/{source}")
        wide = long.pivot(on="metric", index=["node_id", "period_start"], values="value",
                          aggregate_function=None)
        wide = wide.with_columns(pl.lit(None, pl.Float64).alias(m) for m in ("pct", outcome)
                                 if m not in wide.columns)
        one = two_month_mean(wide, [outcome], key=["node_id"],
                             n_periods=rel["period_start"].n_unique())
        parts.append(one.with_columns(release=pl.lit(r)))
    long = pl.concat(parts)
    weight = long.group_by("node_id").agg((pl.col("weight").sum() / len(releases))
                                          .alias("task_weight"))
    obs = long.filter(pl.col(outcome).is_not_null())
    n_rel = obs.group_by("node_id").agg(pl.col("release").n_unique().alias("n_rel"))
    keep = n_rel.filter(pl.col("n_rel") == len(releases) if balanced else pl.col("n_rel") >= 2)
    return (obs.join(keep.select("node_id"), on="node_id", how="semi")
            .join(weight, on="node_id", how="left")
            .select(pl.col("node_id").alias("task_node"), "release",
                    pl.col("release").replace_strict(times, return_dtype=pl.Float64).alias("t"),
                    pl.col(outcome).cast(pl.Float64),
                    pl.col("task_weight").alias("weight"))
            .sort("task_node", pl.col("release").replace_strict(
                {r: i for i, r in enumerate(releases)})))


class _Within:
    """Weighted within-task transformation of a fixed X and the CRV1 pieces that depend on it.

    The sandwich over the full dummy-variable design reduces to the within design: task-dummy
    scores sum to zero within each task, and Σ_g w·x·e = Σ_g w·x̃·e. The correction is
    G/(G-1)·(n-1)/(n-k), k = G + columns of X, as statsmodels' `use_correction`.
    """

    def __init__(self, X: np.ndarray, w: np.ndarray, task: np.ndarray):
        X, w = np.asarray(X, float), np.asarray(w, float)
        if X.ndim == 1:
            X = X[:, None]
        n, p = X.shape
        if w.shape != (n,) or np.asarray(task).shape != (n,):
            raise ValueError("w and task must be 1-D with one value per row of X")
        if not (np.isfinite(X).all() and np.isfinite(w).all()):
            raise ValueError("non-finite X or weights")
        if (w <= 0).any():
            raise ValueError("weights must be positive")
        codes = np.unique(np.asarray(task), return_inverse=True)[1].ravel()
        self.g = int(codes.max()) + 1
        self.n, self.p, self.w = n, p, w
        # Weighted task-sum operator (G x n) and per-task weight totals.
        self.sum_w = sp.csr_matrix((w, (codes, np.arange(n))), shape=(self.g, n))
        self.codes = codes
        self.wtot = np.bincount(codes, weights=w, minlength=self.g)
        self.Xt = self.demean(X)
        A = self.Xt.T @ (self.Xt * w[:, None])
        self.Ainv = np.linalg.inv(A)
        self.correction = (self.g / (self.g - 1)) * (n - 1) / (n - (self.g + p))

    def demean(self, a: np.ndarray) -> np.ndarray:
        means = (self.sum_w @ a) / (self.wtot[:, None] if a.ndim == 2 else self.wtot)
        return a - means[self.codes]

    def fit(self, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        yt = self.demean(np.asarray(y, float))
        beta = self.Ainv @ (self.Xt.T @ (self.w * yt))
        e = yt - self.Xt @ beta
        scores = self.sum_w @ (self.Xt * e[:, None])  # G x p: Σ_g w·x̃·e
        cov = self.correction * self.Ainv @ (scores.T @ scores) @ self.Ainv
        return beta, cov

    def t_stats(self, Y: np.ndarray, j: int) -> np.ndarray:
        """Task-clustered t of column j for every column of Y (n x B), vectorised."""
        Yt = self.demean(Y)
        B = self.Ainv @ (self.Xt.T @ (self.w[:, None] * Yt))  # p x B
        E = Yt - self.Xt @ B
        u = self.Xt @ self.Ainv[:, j]  # a_j' s_g = Σ_g w·u·e
        s = self.sum_w @ (u[:, None] * E)  # G x B
        return B[j] / np.sqrt(self.correction * np.sum(s * s, axis=0))


def clustered_within(y, X, w, task, tested: int) -> tuple[np.ndarray, np.ndarray]:
    """(β, task-clustered CRV1 cov) of the columns of X with task fixed effects.

    Equal to `sm.WLS(y, [X, task dummies], weights=w).fit(cov_type="cluster",
    cov_kwds={"groups": task})` restricted to X's columns. `tested` is the column of X under
    test; it must vary within some task.
    """
    wt = _Within(X, w, task)
    if not 0 <= tested < wt.p:
        raise ValueError(f"tested column {tested} outside X's {wt.p} columns")
    if not np.any(wt.Xt[:, tested] != 0):
        raise ValueError(f"column {tested} does not vary within any task")
    y = np.asarray(y, float)
    if y.shape != (wt.n,) or not np.isfinite(y).all():
        raise ValueError("y must be finite, one value per row of X")
    return wt.fit(y)


def webb_vectors(n_releases: int) -> np.ndarray:
    """Every vector in WEBB^R (6^R x R), in `itertools.product` order."""
    return np.array(list(itertools.product(WEBB, repeat=n_releases)))


def _arrays(df: pl.DataFrame, outcome: str, r6_indicator: bool):
    """Sorted df, releases in calendar order, y, w, task codes, release codes, X columns."""
    need = {"task_node", "release", "t", outcome, "weight"}
    if missing := need - set(df.columns):
        raise ValueError(f"H2 frame lacks {sorted(missing)}")
    df = df.sort("task_node", "release")
    if df.select(list(need)).null_count().sum_horizontal().item():
        raise ValueError("H2 frame has nulls")
    releases = _ordered(df["release"].unique().to_list())
    if len(releases) < 2:
        raise ValueError("H2 needs at least two releases")
    if r6_indicator and "r6" not in releases:
        raise ValueError("r6_indicator needs r6 rows")
    rel = df["release"].to_numpy()
    rcode = np.array([releases.index(r) for r in rel])
    task = np.unique(df["task_node"].to_numpy(), return_inverse=True)[1].ravel()
    extra = (rel == "r6").astype(float)[:, None] if r6_indicator else np.empty((len(df), 0))
    return (df, releases, df[outcome].to_numpy().astype(float),
            df["weight"].to_numpy().astype(float), task, rcode, extra)


def _within_t(y, t, extra, w, task) -> float:
    beta, cov = clustered_within(y, np.column_stack([t, extra]), w, task, tested=0)
    return float(beta[0] / math.sqrt(cov[0, 0]))


def _count_extreme(stats: np.ndarray, observed: float) -> int:
    return int(np.sum(np.abs(stats) >= abs(observed) * (1 - TIE_RTOL)))


def wild_bootstrap_p(df: pl.DataFrame, outcome: str, *,
                     r6_indicator: bool = False) -> tuple[float, int]:
    """Restricted wild cluster bootstrap, clusters = releases, Webb weights (D22 item 3).

    Returns (p, 6^R). Every weight vector is enumerated; the statistic is the task-clustered
    t of the trend.
    """
    df, releases, y, w, task, rcode, extra = _arrays(df, outcome, r6_indicator)
    t = df["t"].to_numpy().astype(float)
    t_obs = _within_t(y, t, extra, w, task)
    full = _Within(np.column_stack([t, extra]), w, task)
    # Restricted fit (β = 0): task FE (+ r6 dummy).
    resid = full.demean(y)
    if extra.shape[1]:
        restricted = _Within(extra, w, task)
        resid = resid - restricted.Xt @ restricted.fit(y)[0]
    fitted0 = y - resid
    V = webb_vectors(len(releases))
    stats = []
    step = max(1, _DRAW_CELLS // len(y))
    for lo in range(0, len(V), step):
        v = V[lo:lo + step][:, rcode].T  # n x b: each row's release weight
        stats.append(full.t_stats(fitted0[:, None] + v * resid[:, None], 0))
    stats = np.concatenate(stats)
    return _count_extreme(stats, t_obs) / len(V), len(V)


def release_label_p(df: pl.DataFrame, outcome: str, *, r6_indicator: bool = False) -> float:
    """Randomisation over release labels (D22 item 4): every permutation of the R time values
    over the R releases, identity included, scored by the task-clustered |t| of the trend.
    Descriptive only; the smallest attainable p is 1/R!."""
    df, releases, y, w, task, rcode, extra = _arrays(df, outcome, r6_indicator)
    times = np.array([df.filter(pl.col("release") == r)["t"][0] for r in releases])
    t_obs = _within_t(y, times[rcode], extra, w, task)
    perms = list(itertools.permutations(range(len(releases))))
    stats = np.array([_within_t(y, times[list(p)][rcode], extra, w, task) for p in perms])
    return _count_extreme(stats, t_obs) / len(perms)


def release_effects(df: pl.DataFrame, outcome: str, base: str = "r2") -> dict[str, Coef]:
    """Release dummies (base `base`) in place of the trend, task FE, task-clustered, 95% CIs."""
    df, releases, y, w, task, rcode, _ = _arrays(df, outcome, False)
    if base not in releases:
        raise ValueError(f"base release {base} not in the frame")
    others = [r for r in releases if r != base]
    X = np.column_stack([(rcode == releases.index(r)).astype(float) for r in others])
    beta, cov = clustered_within(y, X, w, task, tested=0)
    df_inf = int(task.max())  # G_task - 1
    return {r: _t_coef(r, float(beta[i]), float(cov[i, i]), df_inf)
            for i, r in enumerate(others)}


def _primary(y, t, extra, w, task, names):
    """The exact PAP §4.2 call: WLS on [t, task dummies (+ r6 dummy)], task-clustered."""
    g = int(task.max()) + 1
    dummies = (task[:, None] == np.arange(g)).astype(float)
    X = np.column_stack([t, extra, dummies])
    fit = sm.WLS(y, X, weights=w).fit(cov_type="cluster", cov_kwds={"groups": task},
                                      use_t=True)
    df_inf = int(fit.df_resid_inference)
    if df_inf != g - 1:
        raise AssertionError(f"df_resid_inference {df_inf} != G_task - 1 = {g - 1}")
    ci = np.asarray(fit.conf_int(alpha=0.05))
    coefs = {nm: Coef(nm, float(fit.params[i]), float(fit.bse[i]), float(ci[i, 0]),
                      float(ci[i, 1]), float(fit.pvalues[i]), df_inf)
             for i, nm in enumerate(names)}
    return coefs, df_inf, fit


def estimate_h2(df: pl.DataFrame, outcome: str = "automation_pct", *,
                r6_indicator: bool = False) -> HypothesisResult:
    """H2: outcome_tr = α_task + β·t_r (+ r6 dummy) + ε, WLS, fixed task weights (PAP §4.2)."""
    df, releases, y, w, task, rcode, extra = _arrays(df, outcome, r6_indicator)
    t = df["t"].to_numpy().astype(float)
    names = ["trend", *(["r6"] if r6_indicator else [])]
    coefs, df_inf, fit = _primary(y, t, extra, w, task, names)
    beta_w, _ = clustered_within(y, np.column_stack([t, extra]), w, task, tested=0)
    if not np.allclose(beta_w, fit.params[:len(names)], rtol=STATSMODELS_RTOL, atol=0):
        raise AssertionError("within fast path disagrees with the statsmodels fit")

    p_wild, n_draws = wild_bootstrap_p(df, outcome, r6_indicator=r6_indicator)
    p_label = release_label_p(df, outcome, r6_indicator=r6_indicator)
    effects = release_effects(df, outcome) if "r2" in releases else {}
    r = len(releases)
    n_perm = math.factorial(r)
    times = {rel: float(df.filter(pl.col("release") == rel)["t"][0]) for rel in releases}
    notes = [
        f"With {_WORDS.get(r, str(r))} clusters the release-level co-condition is demanding "
        "and may be conservative: H2 can be supported only by a trend that is large relative "
        "to release-to-release variation (D22).",
        'H2 is tested as "measured within-task automation rises across releases" (D22). β is '
        f"the change in measured within-task {outcome} per year, which includes any change in "
        "the classifier and in platform scope (PAP §5).",
        f"H2 is tested alone at α = {ALPHA_H2}: supported only if the task-clustered p ≤ "
        f"{ALPHA_H2}, β > 0 and the release-level wild bootstrap p ≤ {ALPHA_H2}.",
        f"Release-label randomisation over {n_perm} orderings: descriptive only; smallest "
        f"attainable p = 1/{n_perm}.",
        f"Release-level wild bootstrap: full enumeration of 6^{r} = {6**r} Webb vectors; the "
        f"smallest attainable p is 6/{6**r} ≈ {6 / 6**r:.4f}, and near-ties can raise p for "
        "strong trends (PAP D22 design; C-15).",
    ]
    if "r6" in releases and not r6_indicator:
        notes.append("r6 is included without an r6 indicator: the trend is confounded with "
                     "the r6 suppression-regime change (D2).")
    return HypothesisResult(
        hypothesis="H2", outcome=outcome, coefs=coefs, p_family=coefs["trend"].p,
        sample={"n_tasks": int(task.max()) + 1, "n_rows": df.height, "releases": releases,
                "times": times},
        diagnostics={"p_wild": p_wild, "n_wild_draws": n_draws,
                     "p_release_label": p_label, "n_release_orderings": n_perm,
                     "df_inference": df_inf, "g_task": int(task.max()) + 1,
                     "r6_indicator": r6_indicator,
                     "release_effects": {k: {f: getattr(c, f) for f in c.__dataclass_fields__}
                                         for k, c in effects.items()}},
        notes=notes)
