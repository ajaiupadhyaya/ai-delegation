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
from datetime import date

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


# --- whole-run inputs for `aideleg.rq1.confirm` -------------------------------------------

SYNTH_WINDOWS = {"r2": [(date(2025, 2, 24), date(2025, 3, 4))],
                 "r3": [(date(2025, 8, 4), date(2025, 8, 11))],
                 "r4": [(date(2025, 11, 13), date(2025, 11, 20))],
                 "r5": [(date(2026, 2, 5), date(2026, 2, 12))],
                 "r6": [(date(2026, 4, 1), date(2026, 5, 1)),
                        (date(2026, 5, 1), date(2026, 6, 1))]}
SYNTH_SOC6 = ("11-1021", "13-2011", "15-1252", "23-1011", "25-1021", "29-1141", "41-2031",
              "43-4051", "47-2061", "53-3032")
SYNTH_COUNTRIES = ("ARG", "AUS", "BRA", "CAN", "DEU", "FRA", "GBR", "IND", "JPN", "NAM",
                   "NGA", "USA")
_PATTERNS = ("directive_pct", "feedback_loop_pct", "task_iteration_pct", "validation_pct",
             "learning_pct")


def _patterns(rng: np.random.Generator) -> dict[str, float]:
    """Five renormalised patterns (sum 100), their buckets and the suppression shares."""
    raw = rng.dirichlet(np.ones(5)) * 100
    out = dict(zip(_PATTERNS, map(float, raw), strict=True))
    out["automation_pct"] = out["directive_pct"] + out["feedback_loop_pct"]
    out["augmentation_pct"] = 100 - out["automation_pct"]
    out["none_pct"] = float(rng.uniform(1, 10))
    out["filtered_pct"] = float(rng.uniform(1, 10))
    out["not_classified_pct"] = float(rng.uniform(1, 10))
    out["ai_autonomy_mean"] = float(rng.uniform(1, 5))
    return out


def synthetic_inputs(seed: int = 7, *, n_task: int = 40, n_family: int = 5):
    """A small, complete `confirm.Inputs`: r2-r6 global tasks, r6 country overall and GWA
    rows, families, wages and GDP/WAP frames. Nothing here reads AEI data."""
    from aideleg.aei.schema import PANEL_COLUMNS
    from aideleg.aei.tasks import TaskIndex, normalise_task_text
    from aideleg.rq1.confirm import Inputs

    rng = np.random.default_rng(seed)
    recs: list[tuple] = []

    def add(rel, start, end, geo_level, geo_id, taxonomy, node_id, metric, value):
        recs.append((rel, start, end, "claude_ai", geo_level, geo_id, taxonomy, 0, node_id,
                     node_id if taxonomy != "onet_task" else f"Task statement {node_id}.",
                     metric, float(value), "collab_v2"))

    ids_by_text, occ_by_id, fam_rows = {}, {}, []
    for t in range(n_task):
        tid = 1000 + t
        k = int(rng.integers(1, 4))
        occ_by_id[tid] = sorted(f"{s}.00" for s in rng.choice(SYNTH_SOC6, k, replace=False))
        ids_by_text[normalise_task_text(f"Task statement {tid}.")] = [tid]
        for f in rng.choice(n_family, int(rng.integers(1, 3)), replace=False):
            fam_rows.append((tid, f"iwa{int(f):02d}"))
        educ = float(rng.uniform(10, 20))
        for rel, windows in SYNTH_WINDOWS.items():
            for start, end in windows:
                values = {"pct": float(rng.uniform(0.1, 2.0)), **_patterns(rng)}
                if rel == "r6":
                    values["human_education_years_mean"] = educ
                for m, v in values.items():
                    add(rel, start, end, "global", "GLOBAL", "onet_task", str(tid), m, v)

    gwas = ("g1", "g2", "g3")
    for start, end in SYNTH_WINDOWS["r6"]:
        add("r6", start, end, "global", "GLOBAL", "overall", "overall", "automation_pct", 45.0)
        for g in gwas:
            add("r6", start, end, "global", "GLOBAL", "onet_gwa", g, "pct", 100 / 3)
            add("r6", start, end, "global", "GLOBAL", "onet_gwa", g, "automation_pct",
                rng.uniform(20, 70))
        for c in SYNTH_COUNTRIES:
            vals = {**_patterns(rng), "usage_per_capita_index": rng.uniform(0.2, 5.0),
                    "usage_pct": rng.uniform(0.1, 5.0)}
            for m in ("automation_pct", "usage_per_capita_index", "usage_pct",
                      "validation_pct", "ai_autonomy_mean"):
                add("r6", start, end, "country", c, "overall", "overall", m, vals[m])
            for g, s in zip(gwas, rng.dirichlet(np.ones(3)) * 100, strict=True):
                add("r6", start, end, "country", c, "onet_gwa", g, "pct", s)

    schema = {c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                  else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS}
    panel = pl.DataFrame(recs, schema=schema, orient="row")
    families = pl.DataFrame(fam_rows, schema={"task_id": pl.Int64, "family": pl.String},
                            orient="row").unique().sort("task_id", "family")
    medians = rng.uniform(30_000, 200_000, len(SYNTH_SOC6))
    wages = pl.DataFrame({"soc6": list(SYNTH_SOC6), "tot_emp": [1000] * len(SYNTH_SOC6),
                          "a_median": medians,
                          "a_median_status": ["published"] * len(SYNTH_SOC6)})
    gdp = pl.DataFrame({"iso_alpha_3": list(SYNTH_COUNTRIES), "year": "2024",
                        "gdp_total": [str(x) for x in rng.uniform(1e10, 1e13, 12)]})
    wap = pl.DataFrame({"iso_alpha_3": list(SYNTH_COUNTRIES), "year": "2024",
                        "working_age_pop": [str(x) for x in rng.uniform(1e6, 1e8, 12)]})
    return Inputs(panel=panel, index=TaskIndex(ids_by_text, occ_by_id), families=families,
                  wages=wages, oews_codes=set(SYNTH_SOC6), soc_structure=None,
                  gdp_country=gdp, wap_country=wap)
