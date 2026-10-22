"""H4: geography (PAP §4.4, D16, D17).

AEI data are conversations matched to O*NET tasks. A row here is one geography's conversations
in release r6 (`claude_ai`): its overall share of automation-pattern conversations, its usage
index (AUI) and its GDP per working-age person.

Rules
- **Geographies.** `geo="country"`: `geo_level == "country"`, ISO-3 `geo_id`. `geo="us_state"`:
  `geo_level == "subregion"` with `geo_id` starting `US-` (R28).
- **Releases.** The release must publish the geography's overall `usage_per_capita_index` and
  its `onet_gwa` (or `onet_iwa`) `pct` rows, else `ValueError` naming what is missing. r4 and
  r5 publish neither for countries; their R28 samples are built by Plan 4, which calls
  `estimate_h4` here.
- **Months, then logs.** `automation_pct`, `aui` (`usage_per_capita_index`), `usage_pct`,
  `validation_pct` and `ai_autonomy_mean` come from the `overall` taxonomy, each the
  equal-weighted mean of the published monthly values. A geography needs every month of
  `automation_pct` and `aui` (reason `missing_month`). Logs are of the two-month mean.
- **Income.** GDP 2024 / working-age (15-64) population 2024, from the AEI r3 inputs. Countries
  join on the `iso_alpha_3` string, states on `"US-" + state_code`; the CSVs are read as
  strings (`infer_schema_length=0`) so Namibia's `NA` is never a null. A null income is reason
  `missing_income` when `require_income`, else the geography is kept with a null income.
  Kosovo is `XKX` in the AEI files and in the GDP and population files alike, so no recoding
  is needed here (only a Natural Earth join maps `XKX` to `KOS`).
- **Task-mix control.** M_c = Σ_g s̄_cg·ā_g. s_cg is the geography's `pct` over the mix nodes,
  renormalised over the nodes published in that month (unpublished = 0); s̄ is the mean over
  the months; ā_g is the global `automation_pct` of node g by `two_month_mean` (weights: its
  global `pct`). The sum runs over nodes with a published ā_g, with s̄ renormalised over them.
  No such node: reason `missing_mix`. `m_global` applies the same formula to the global shares.
- **Exclusions.** Every geography of the requested level is either in the frame or listed in
  `excluded` under its first failing reason, in the order of `EXCLUSION_REASONS`.
- **Estimator** (`estimate_h4`). `OLS(y, [1, log_aui, log_income, mix]).fit(cov_type="HC3")`
  (`WLS` with `weights`, R28). `p_family` is the joint HC3 Wald F test of the two predictors
  (D17), with (2, n - 4) df. Coefficients carry normal-reference HC3 p-values and 95% CIs.
- **Shift-share** (descriptive). gap = automation - global = (M - global) + (automation - M).
  `mix_part` carries the common offset m_global - global, printed alongside.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np
import polars as pl
import statsmodels.api as sm

from aideleg.acquire.sources import by_key
from aideleg.config import RAW
from aideleg.rq1.inputs import two_month_mean
from aideleg.rq1.result import Coef, HypothesisResult

REQUIRED = ("automation_pct", "usage_per_capita_index")
CARRIED = ("usage_pct", "validation_pct", "ai_autonomy_mean")
EXCLUSION_REASONS = ("missing_month", "missing_income", "missing_mix")
FRAME_COLUMNS = ["geo_id", "automation_pct", "aui", "log_aui", "income", "log_income", "mix",
                 "usage_pct", "validation_pct", "ai_autonomy_mean"]
_GEO = {"country": ("country", None), "us_state": ("subregion", "US-")}
_MIX_TAXONOMY = {"gwa": "onet_gwa", "iwa": "onet_iwa"}
_INCOME_KEYS = {"country": ("aei_geo_gdp_country", "aei_geo_wap_country"),
                "us_state": ("aei_geo_gdp_us_state", "aei_geo_wap_us_state")}


@dataclass(frozen=True)
class GeoSample:
    frame: pl.DataFrame
    excluded: dict[str, list[str]]  # reason -> geo_ids
    global_automation: float  # global overall automation_pct, mean over the months
    m_global: float  # the mix formula applied to the global shares


def read_income_csv(path: Path) -> pl.DataFrame:
    """An AEI GDP or working-age population CSV, every column a string."""
    return pl.read_csv(path, infer_schema_length=0)


def _income(geo: str, gdp: pl.DataFrame, wap: pl.DataFrame) -> pl.DataFrame:
    """`geo_id, income`: GDP / working-age population, null if either is missing or not > 0."""
    def keyed(df: pl.DataFrame, value: str, what: str) -> pl.DataFrame:
        key = (pl.col("iso_alpha_3") if geo == "country"
               else pl.lit("US-") + pl.col("state_code"))
        out = df.select(key.cast(pl.String).alias("geo_id"),
                        pl.col(value).cast(pl.String).cast(pl.Float64, strict=False)
                        .alias(value))
        dup = out.filter(pl.col("geo_id").is_duplicated())["geo_id"].unique().to_list()
        if dup:
            raise ValueError(f"duplicate {what} rows for {sorted(dup)[:5]}")
        return out

    g = keyed(gdp, "gdp_total", "GDP")
    w = keyed(wap, "working_age_pop", "working-age population")
    ok = (pl.col("gdp_total") > 0) & (pl.col("working_age_pop") > 0)
    return (g.join(w, on="geo_id", how="full", coalesce=True)
            .select("geo_id", income=pl.when(ok).then(pl.col("gdp_total")
                                                      / pl.col("working_age_pop"))))


def _mix(pct: pl.DataFrame, a_bar: pl.DataFrame, n_periods: int) -> pl.DataFrame:
    """`geo_id, mix` from long `geo_id, node_id, period_start, pct` rows and `node_id, a_bar`."""
    s = (pct.filter(pl.col("pct").is_not_null() & (pl.col("pct") >= 0))
         .with_columns(den=pl.col("pct").sum().over("geo_id", "period_start"))
         .filter(pl.col("den") > 0)
         .with_columns(s=pl.col("pct") / pl.col("den")))
    s_bar = s.group_by("geo_id", "node_id").agg((pl.col("s").sum() / n_periods).alias("s_bar"))
    return (s_bar.join(a_bar, on="node_id", how="inner")
            .group_by("geo_id")
            .agg(num=(pl.col("s_bar") * pl.col("a_bar")).sum(), den=pl.col("s_bar").sum())
            .filter(pl.col("den") > 0)
            .select("geo_id", mix=pl.col("num") / pl.col("den")))


def _wide(long: pl.DataFrame, metrics: Sequence[str], index: list[str]) -> pl.DataFrame:
    if long.select(index + ["metric"]).is_duplicated().any():
        raise ValueError("duplicate panel rows")
    wide = long.pivot(on="metric", index=index, values="value", aggregate_function=None)
    return wide.with_columns(pl.lit(None, pl.Float64).alias(m) for m in metrics
                             if m not in wide.columns)


def build_geo_sample(panel: pl.DataFrame, *, release: str = "r6", source: str = "claude_ai",
                     geo: Literal["country", "us_state"] = "country",
                     mix_level: Literal["gwa", "iwa"] = "gwa", require_income: bool = True,
                     gdp: pl.DataFrame | None = None,
                     wap: pl.DataFrame | None = None) -> GeoSample:
    """The H4 cross-section of `release`/`source` at `geo` level (D16)."""
    if geo not in _GEO:
        raise ValueError(f"unknown geo {geo!r}")
    if mix_level not in _MIX_TAXONOMY:
        raise ValueError(f"unknown mix_level {mix_level!r}")
    level, prefix = _GEO[geo]
    taxonomy = _MIX_TAXONOMY[mix_level]
    rel = panel.filter((pl.col("release") == release) & (pl.col("source") == source))
    n_periods = rel["period_start"].n_unique()
    if n_periods == 0:
        raise ValueError(f"no rows for {release}/{source}")
    geo_rows = rel.filter(pl.col("geo_level") == level)
    if prefix:
        geo_rows = geo_rows.filter(pl.col("geo_id").str.starts_with(prefix))
    overall = geo_rows.filter((pl.col("taxonomy") == "overall")
                              & pl.col("metric").is_in(REQUIRED + CARRIED))
    mix_pct = geo_rows.filter((pl.col("taxonomy") == taxonomy) & (pl.col("metric") == "pct"))
    glob = rel.filter(pl.col("geo_level") == "global")
    g_overall = glob.filter((pl.col("taxonomy") == "overall")
                            & (pl.col("metric") == "automation_pct"))
    g_mix = glob.filter((pl.col("taxonomy") == taxonomy)
                        & pl.col("metric").is_in(["pct", "automation_pct"]))
    for m in REQUIRED:
        if not (overall["metric"] == m).any():
            raise ValueError(f"{release}/{source} publishes no {geo} overall {m}")
    if mix_pct.is_empty():
        raise ValueError(f"{release}/{source} publishes no {geo} {taxonomy} pct rows")
    if g_overall.is_empty():
        raise ValueError(f"{release}/{source} publishes no global overall automation_pct")
    if not (g_mix["metric"] == "pct").any():
        raise ValueError(f"{release}/{source} publishes no global {taxonomy} pct")
    if not (g_mix["metric"] == "automation_pct").any():
        raise ValueError(f"{release}/{source} publishes no global {taxonomy} automation_pct")

    # Equal-weighted means over the published months; counts for the inclusion rule.
    wide = _wide(overall, REQUIRED + CARRIED, ["geo_id", "period_start"])
    base = wide.group_by("geo_id").agg(
        *[pl.col(m).mean() for m in REQUIRED + CARRIED],
        *[pl.col(m).is_not_null().sum().alias(f"n_{m}") for m in REQUIRED])

    g_wide = _wide(g_mix, ["pct", "automation_pct"], ["node_id", "period_start"])
    a_bar = (two_month_mean(g_wide, ["automation_pct"], key=["node_id"], n_periods=n_periods)
             .filter(pl.col("automation_pct").is_not_null())
             .select("node_id", a_bar="automation_pct"))
    mix = _mix(mix_pct.select("geo_id", "node_id", "period_start", pct="value"), a_bar,
               n_periods)
    g_pct = g_wide.select(pl.lit("GLOBAL").alias("geo_id"), "node_id", "period_start", "pct")
    m_global = _mix(g_pct, a_bar, n_periods)["mix"]
    if len(m_global) != 1:
        raise ValueError(f"m_global: no global {taxonomy} node has both pct and automation_pct")
    global_automation = g_overall["value"].drop_nulls().mean()

    if gdp is None or wap is None:
        gdp_key, wap_key = _INCOME_KEYS[geo]
        gdp = gdp if gdp is not None else read_income_csv(RAW / by_key(gdp_key).dest)
        wap = wap if wap is not None else read_income_csv(RAW / by_key(wap_key).dest)
    income = _income(geo, gdp, wap)

    universe = geo_rows.select("geo_id").unique()
    df = (universe.join(base, on="geo_id", how="left")
          .join(mix, on="geo_id", how="left")
          .join(income, on="geo_id", how="left")
          .sort("geo_id"))
    tests = {
        "missing_month": pl.any_horizontal(
            pl.col(f"n_{m}").fill_null(0) < n_periods for m in REQUIRED),
        "missing_income": (pl.col("income").is_null() if require_income else pl.lit(False)),
        "missing_mix": pl.col("mix").is_null(),
    }
    excluded: dict[str, list[str]] = {}
    for reason in EXCLUSION_REASONS:
        hit = df.filter(tests[reason])
        excluded[reason] = hit["geo_id"].to_list()
        df = df.filter(~tests[reason])
    bad = df.filter(pl.col("usage_per_capita_index") <= 0)["geo_id"].to_list()
    if bad:
        raise ValueError(f"non-positive usage_per_capita_index for {bad[:5]}")
    frame = df.select(
        "geo_id", "automation_pct", aui="usage_per_capita_index",
        log_aui=pl.col("usage_per_capita_index").log(), income="income",
        log_income=pl.col("income").log(), mix="mix", usage_pct="usage_pct",
        validation_pct="validation_pct", ai_autonomy_mean="ai_autonomy_mean",
    ).select(FRAME_COLUMNS)
    return GeoSample(frame=frame, excluded=excluded,
                     global_automation=float(global_automation),
                     m_global=float(m_global[0]))


def estimate_h4(frame: pl.DataFrame, outcome: str = "automation_pct",
                predictors: tuple[str, str] = ("log_aui", "log_income"), control: str = "mix",
                weights: str | None = None) -> HypothesisResult:
    """H4 (PAP §4.4): OLS (WLS with `weights`) with HC3; p = joint Wald of `predictors` (D17)."""
    if len(predictors) != 2:
        raise ValueError(f"H4 tests two predictors, got {predictors}")
    names = [*predictors, control]
    used = [outcome, *names] + ([weights] if weights else [])
    missing = [c for c in used if c not in frame.columns]
    if missing:
        raise ValueError(f"estimate_h4: columns not in frame: {missing}")
    for c in used:
        x = frame[c].cast(pl.Float64)
        if x.null_count() or not np.isfinite(x.to_numpy()).all():
            raise ValueError(f"estimate_h4: null or non-finite {c}")
    n = frame.height
    if n <= len(names) + 1:
        raise ValueError(f"estimate_h4: n = {n} is too small")
    y = frame[outcome].cast(pl.Float64).to_numpy()
    X = np.column_stack([np.ones(n)] + [frame[c].cast(pl.Float64).to_numpy() for c in names])
    if weights:
        w = frame[weights].cast(pl.Float64).to_numpy()
        if (w <= 0).any():
            raise ValueError(f"estimate_h4: non-positive {weights}")
        fit = sm.WLS(y, X, weights=w).fit(cov_type="HC3")
    else:
        fit = sm.OLS(y, X).fit(cov_type="HC3")
    R = np.zeros((2, X.shape[1]))
    R[0, 1] = R[1, 2] = 1.0
    wald = fit.wald_test(R, use_f=True, scalar=True)
    ci = fit.conf_int(alpha=0.05)
    coefs = {c: Coef(name=c, estimate=float(fit.params[i]), se=float(fit.bse[i]),
                     ci_low=float(ci[i, 0]), ci_high=float(ci[i, 1]),
                     p=float(fit.pvalues[i]), df=None)
             for i, c in enumerate(names, start=1)}
    return HypothesisResult(
        hypothesis="H4", outcome=outcome, coefs=coefs, p_family=float(wald.pvalue),
        sample={"n": n},
        diagnostics={"F": float(wald.statistic), "df_num": int(wald.df_num),
                     "df_denom": int(wald.df_denom), "cov_type": "HC3",
                     "estimator": "WLS" if weights else "OLS", "weights": weights,
                     "tested": list(predictors), "control": control})


def shift_share(frame: pl.DataFrame, global_automation: float, *,
                m_global: float) -> pl.DataFrame:
    """Descriptive split of each geography's gap from the global share (PAP §4.4).

    `m_global` is in general not equal to `global_automation`, so every `mix_part` carries the
    common offset `m_global - global_automation`; it is printed alongside on every row.
    """
    g, m = float(global_automation), float(m_global)
    return frame.select(
        "geo_id",
        gap=pl.col("automation_pct") - g,
        mix_part=pl.col("mix") - g,
        within_part=pl.col("automation_pct") - pl.col("mix"),
        global_automation=pl.lit(g),
        m_global=pl.lit(m),
        offset=pl.lit(m - g),
    )
