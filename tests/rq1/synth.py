"""Synthetic H1/H3 inputs for tests. Nothing here reads AEI data.

`task_rows` builds a `TaskRows` with the same columns as `rows.build_task_rows`. Each task gets
1-3 occupations and 1-2 families; its weight is split equally over its (occupation, family)
rows, so usage is conserved. Every outcome is constant within a task, with noise sd 5.

Planted effects:
- `automation_pct` = 50 + beta_educ·(education - 14) + beta_wage·(mean log wage - 11) + family
  effect + noise, where the mean log wage is the task's allocation-weighted (equal-weight) mean
  over its occupations with a wage (the effective regressor of PAP §4.1 P13).
- `validation_pct` = 20 + gamma·(task's allocation-weighted mean error_cost) + family effect +
  noise. With `pure_error_cost_tasks=True` each task's occupations are all error-cost or all
  not, so the indicator is constant within a task.

Occupation 0 has no OEWS code, occupation 1 a suppressed wage, occupation 2 a top-coded wage.
"""

import math

import numpy as np
import polars as pl

from aideleg.rq1.rows import DROP_REASONS, OUTCOME_COLUMNS, ROW_COLUMNS, TaskRows

NOISE_SD = 5.0
WAGE_MEAN, WAGE_SD = 11.0, 1.5
EDUC_MEAN, EDUC_SD = 14.0, 3.0
TOPCODE = 239_200.0


def _occupations(rng: np.random.Generator, n_occ: int) -> pl.DataFrame:
    soc6 = [f"99-{i:04d}" for i in range(n_occ)]
    log_wage = rng.normal(WAGE_MEAN, WAGE_SD, n_occ)
    status = ["published"] * n_occ
    oews = list(soc6)
    wages: list[float | None] = list(log_wage)
    status[0], oews[0], wages[0] = "no_oews_code", None, None
    status[1], wages[1] = "suppressed", None
    status[2], wages[2] = "topcoded", math.log(TOPCODE)
    error_cost = (rng.random(n_occ) < 0.4).astype(np.int8)
    error_cost[:2] = [1, 0]  # both pools are non-empty
    return pl.DataFrame({"soc6": soc6, "oews_code": oews, "log_wage": wages,
                         "wage_status": status, "error_cost": error_cost},
                        schema={"soc6": pl.String, "oews_code": pl.String,
                                "log_wage": pl.Float64, "wage_status": pl.String,
                                "error_cost": pl.Int8})


def task_rows(seed: int, *, n_occ: int = 40, n_task: int = 400, n_family: int = 20,
              beta_educ: float = 0.0, beta_wage: float = 0.0, gamma: float = 0.0,
              pure_error_cost_tasks: bool = False) -> TaskRows:
    rng = np.random.default_rng(seed)
    occ = _occupations(rng, n_occ)
    wage = occ["log_wage"].to_numpy()
    ec = occ["error_cost"].to_numpy()
    pools = [np.flatnonzero(ec == 1), np.flatnonzero(ec == 0)]
    fam_effect = rng.normal(0.0, 5.0, n_family)
    fam_effect_v = rng.normal(0.0, 5.0, n_family)

    recs = []
    for t in range(n_task):
        k_occ, k_fam = int(rng.integers(1, 4)), int(rng.integers(1, 3))
        pool = pools[int(rng.random() >= 0.4)] if pure_error_cost_tasks else np.arange(n_occ)
        occs = np.sort(rng.choice(pool, size=min(k_occ, len(pool)), replace=False))
        fams = np.sort(rng.choice(n_family, size=k_fam, replace=False))
        fe, fe_v = fam_effect[fams].mean(), fam_effect_v[fams].mean()
        educ = EDUC_MEAN + rng.normal(0.0, EDUC_SD)
        w_known = wage[occs][~np.isnan(wage[occs])]
        wage_bar = w_known.mean() if len(w_known) else WAGE_MEAN
        values = {
            "automation_pct": 50 + beta_educ * (educ - EDUC_MEAN)
            + beta_wage * (wage_bar - WAGE_MEAN) + fe + rng.normal(0.0, NOISE_SD),
            "validation_pct": 20 + gamma * ec[occs].mean() + fe_v + rng.normal(0.0, NOISE_SD),
        }
        for c in OUTCOME_COLUMNS:
            values.setdefault(c, 30 + rng.normal(0.0, NOISE_SD))
        values["automation_share_all_lb"] = values["automation_pct"] * 0.98
        values["automation_share_all_ub"] = values["automation_share_all_lb"] + 2.0
        weight = float(rng.uniform(0.5, 2.0))
        for o in occs:
            for f in fams:
                recs.append({"task_node": f"{t:05d}", "soc6": occ["soc6"][int(o)],
                             "family": f"iwa{f:02d}",
                             "weight": weight / (len(occs) * len(fams)),
                             "n_occ": len(occs), "n_family": len(fams),
                             "human_education_years_mean": educ, **values})

    rows = (pl.DataFrame(recs)
            .join(occ, on="soc6", how="left")
            .with_columns(task_code=(pl.col("task_node").rank("dense") - 1).cast(pl.Int64),
                          occ_code=(pl.col("soc6").rank("dense") - 1).cast(pl.Int64),
                          n_occ=pl.col("n_occ").cast(pl.Int64),
                          n_family=pl.col("n_family").cast(pl.Int64))
            .select(ROW_COLUMNS)
            .sort("task_node", "soc6", "family"))
    total = float(rows["weight"].sum())
    return TaskRows(rows, total, {r: 0.0 for r in DROP_REASONS}, {r: 0 for r in DROP_REASONS})


H2_TIMES = {"r2": 0.0, "r3": 0.4394250513347023, "r4": 0.7159479808350445,
            "r5": 0.945927446954141}


def h2_frame(alpha: np.ndarray, release_values: dict[str, np.ndarray],
             weight: np.ndarray | None = None, times: dict[str, float] | None = None,
             outcome: str = "automation_pct") -> pl.DataFrame:
    """A balanced `build_h2_panel`-shaped frame: one row per (task, release).

    `alpha` holds the task effects; `release_values[r]` is added to them in release r (a
    per-task array: trend, release shock and noise, as the test builds it). `weight` is per
    task (default 1.0). Nothing here reads AEI data.
    """
    times = times or H2_TIMES
    n = len(alpha)
    w = np.ones(n) if weight is None else np.asarray(weight, float)
    parts = [pl.DataFrame({"task_node": [f"{i:05d}" for i in range(n)],
                           "release": r, "t": times[r],
                           outcome: alpha + np.asarray(v, float), "weight": w})
             for r, v in release_values.items()]
    return pl.concat(parts).sort("task_node", "release")
