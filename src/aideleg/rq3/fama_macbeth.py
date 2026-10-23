"""Fama-MacBeth cross-sectional regressions (PAP §8.3, exploratory; §11 C-35, C-38).

- Panel: for each month end t in the window and each FF49 industry,
  - `ret_x` = the FF49 monthly value-weighted industry return minus rf (the FF5 monthly file's
    rf, matched by date), in percent (PAP §3.1);
  - `z` = the design's `z_delegation` (conversations matched to O*NET tasks, aggregated to
    FF49), as given: not re-standardised per month or after drops;
  - `log_size` = ln(`avg_size`) of the `characteristics` row whose `me_date` is the month end
    before t (PAP §11 C-35; `data.SIZE_ME_OFFSET`);
  - `log_beme` = ln("Sum of BE / Sum of ME") of the row for `beme_year(t)`, French's July-June
    timing (PAP §11 C-38): the row for year y is BE for fiscal y - 1 over ME at December y - 1,
    used from July y to June y + 1;
  - `mom` = the 12-2 cumulative return, prod_{s=t-12}^{t-2} (1 + r_s / 100) - 1 (a decimal),
    from the same value-weighted industry returns; null unless all 11 are present.
  A non-positive or missing `avg_size` or BE/ME, a missing or NaN return, or a missing exposure
  gives a null value, and that industry leaves that month's regression.
- Each month: OLS of `ret_x` on [1, regressors] over the industries with every value. A month
  with n <= len(regressors) + 1 such industries is skipped and counted (C-38); a rank-deficient
  month, or fewer than 2 months left, makes the run refuse.
- Per regressor: the time-series mean of the monthly slopes with a Newey-West SE
  (`stats.hac_regression(coefs, None)`, lag floor(4 (T/100)^(2/9)), no small-sample
  correction), t-based p and a 95% CI from the t distribution with T - 1 df.
- Units: the slope on z is pp per month per 1 SD of exposure (x 12 shown beside it in the doc);
  the others are pp per month per unit of the regressor.

A_pooled is labelled look-ahead (D19). Market data are read only through the guarded loaders in
`aideleg.rq3.data`. AEI data are conversations matched to O*NET tasks; nothing here speaks to
the labour market.
"""

import math
from collections.abc import Sequence
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
from scipy import stats as _st

from aideleg.results.common import WORDING, check_text, generated_line, write_csv
from aideleg.rq3 import data, stats
from aideleg.rq3.report import fmt_p, identical_exposure, zero_assigned_bullets
from aideleg.rq3.terciles import WINDOWS, window_months

GENERATOR = "uv run python -m aideleg.rq3 fm"
HEADING = "# Fama–MacBeth (exploratory, PAP §8.3)"
REGRESSORS: tuple[str, ...] = ("z", "log_size", "log_beme", "mom")
RUNS: tuple[tuple[str, str], ...] = (("B", "B"), ("A_r2", "A"), ("A_pooled", "A"))
LOOK_AHEAD = "A_pooled"
PERIODS = 12
EXPOSURE_COL = "z_delegation"
COLUMNS = ["design", "window", "regressor", "mean", "se", "ci_lo", "ci_hi", "p", "T", "n_mean",
           "skipped"]
PANEL_COLUMNS = ["date", "ff49_short", "ret_x", "z", "log_size", "log_beme", "mom"]


def _midx(d: date) -> int:
    return d.year * 12 + d.month - 1


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def _log_pos(x) -> float | None:
    return math.log(x) if _ok(x) and x > 0 else None


def momentum_12_2(monthly_ret: pl.DataFrame) -> pl.DataFrame:
    """`date, ff49_short, mom` for every date and industry of the wide `monthly_ret` (percent).

    mom_t = prod_{s=t-12}^{t-2} (1 + r_s / 100) - 1, by calendar month; null unless all 11
    returns are present (a month absent from the frame counts as missing)."""
    names = [c for c in monthly_ret.columns if c != "date"]
    df = monthly_ret.sort("date")
    dates = df["date"].to_list()
    out: dict[str, list] = {"date": [], "ff49_short": [], "mom": []}
    for nm in names:
        by_m = dict(zip((_midx(d) for d in dates), df[nm].to_list(), strict=True))
        for t in dates:
            k = _midx(t)
            rs = [by_m.get(k - s) for s in range(2, 13)]
            mom = None
            if all(_ok(r) for r in rs):
                mom = float(np.prod([1 + r / 100 for r in rs]) - 1)
            out["date"].append(t)
            out["ff49_short"].append(nm)
            out["mom"].append(mom)
    return pl.DataFrame(out, schema={"date": pl.Date, "ff49_short": pl.String,
                                     "mom": pl.Float64}).sort("date", "ff49_short")


def beme_year(d: date) -> int:
    """The French BE/ME row used in month `d`: July y to June y + 1 use the row for year y."""
    return d.year if d.month >= 7 else d.year - 1


def _prior_month_end(t: date) -> date:
    return date.fromordinal(t.replace(day=1).toordinal() - 1)


def _build_panel(expo: pl.DataFrame, months: Sequence[date], ret: pl.DataFrame,
                 factors: pl.DataFrame, chars: pl.DataFrame, be: pl.DataFrame,
                 mom: pl.DataFrame) -> pl.DataFrame:
    designs = set(expo["design"].to_list())
    if len(designs) > 1:
        raise ValueError(f"fm_panel needs one design's exposure frame, got {sorted(designs)}")
    names = [c for c in ret.columns if c != "date"]
    rows = {r["date"]: r for r in ret.iter_rows(named=True)}
    rf = dict(zip(factors["date"].to_list(), factors["rf"].to_list(), strict=True))
    z = {r["ff49_short"]: r[EXPOSURE_COL] for r in expo.iter_rows(named=True)}
    size = {(r["me_date"], r["ff49_short"]): r["avg_size"]
            for r in chars.select("me_date", "ff49_short", "avg_size").iter_rows(named=True)}
    bm = {(r["year"], r["ff49_short"]): r["beme"] for r in be.iter_rows(named=True)}
    mm = {(r["date"], r["ff49_short"]): r["mom"] for r in mom.iter_rows(named=True)}
    out: dict[str, list] = {c: [] for c in PANEL_COLUMNS}
    for t in sorted(months):
        if t not in rows:
            raise ValueError(f"month {t} not in the industry returns")
        if not _ok(rf.get(t)):
            raise ValueError(f"month {t}: no rf in the factor file")
        me = _prior_month_end(t)
        y = beme_year(t)
        for nm in names:
            r = rows[t][nm]
            zj = z.get(nm)
            out["date"].append(t)
            out["ff49_short"].append(nm)
            out["ret_x"].append(float(r) - float(rf[t]) if _ok(r) else None)
            out["z"].append(float(zj) if _ok(zj) else None)
            out["log_size"].append(_log_pos(size.get((me, nm))))
            out["log_beme"].append(_log_pos(bm.get((y, nm))))
            m = mm.get((t, nm))
            out["mom"].append(float(m) if _ok(m) else None)
    schema = {"date": pl.Date, "ff49_short": pl.String,
              **{c: pl.Float64 for c in PANEL_COLUMNS[2:]}}
    return pl.DataFrame(out, schema=schema)


def fm_panel(expo: pl.DataFrame, months: Sequence[date]) -> pl.DataFrame:
    """`date, ff49_short, ret_x, z, log_size, log_beme, mom` for one design and `months`."""
    ret, factors = data.monthly("VW")
    return _build_panel(expo, months, ret, factors, data.characteristics(), data.beme(),
                        momentum_12_2(ret))


def _complete(g: pl.DataFrame, regressors: Sequence[str]) -> pl.DataFrame:
    return g.drop_nulls(["ret_x", *regressors]).filter(
        pl.all_horizontal(pl.col(c).is_not_nan() for c in ["ret_x", *regressors]))


def monthly_slopes(panel: pl.DataFrame, regressors: Sequence[str] = REGRESSORS
                   ) -> tuple[pl.DataFrame, list[date]]:
    """Per-month OLS slopes (`date, n, <regressors>`) and the skipped months."""
    regressors = list(regressors)
    k = len(regressors)
    out: dict[str, list] = {"date": [], "n": [], **{r: [] for r in regressors}}
    skipped: list[date] = []
    for t in sorted(set(panel["date"].to_list())):
        g = _complete(panel.filter(pl.col("date") == t).sort("ff49_short"), regressors)
        if g.height <= k + 1:
            skipped.append(t)
            continue
        X = np.column_stack([np.ones(g.height), g.select(regressors).to_numpy()])
        if np.linalg.matrix_rank(X) < k + 1:
            raise ValueError(f"month {t}: the regressor matrix is rank-deficient")
        b = np.linalg.lstsq(X, g["ret_x"].to_numpy(), rcond=None)[0]
        out["date"].append(t)
        out["n"].append(g.height)
        for i, r in enumerate(regressors):
            out[r].append(float(b[i + 1]))
    schema = {"date": pl.Date, "n": pl.Int64, **{r: pl.Float64 for r in regressors}}
    return pl.DataFrame(out, schema=schema), skipped


def fama_macbeth(panel: pl.DataFrame, regressors: Sequence[str] = REGRESSORS
                 ) -> dict[str, dict]:
    """Per regressor: `mean, se, ci95, p, T, n_mean, skipped` of the monthly slopes, plus
    `skipped_months` (the skipped month ends) and the NW `lag`."""
    slopes, skipped = monthly_slopes(panel, regressors)
    T = slopes.height
    if T < 2:
        raise ValueError(f"only {T} month(s) with enough complete industries "
                         f"({len(skipped)} skipped); Fama-MacBeth needs at least 2")
    tc = float(_st.t.ppf(0.975, T - 1))
    n_mean = float(slopes["n"].mean())
    out = {}
    for r in regressors:
        c = slopes[r].to_numpy()
        h = stats.hac_regression(c, None)
        mean, se = float(np.mean(c)), float(h["se"][0])
        out[r] = {"mean": mean, "se": se, "ci95": (mean - tc * se, mean + tc * se),
                  "p": float(h["p"][0]), "T": T, "n_mean": n_mean, "skipped": len(skipped),
                  "skipped_months": list(skipped), "lag": h["lag"]}
    return out


# --- report ----------------------------------------------------------------------------


def _label(design: str) -> str:
    return f"{design} (look-ahead)" if design == LOOK_AHEAD else design


def _method_lines() -> list[str]:
    return [
        "- Dependent variable: the FF49 monthly value-weighted industry return minus rf (FF5 "
        "monthly file, matched by date), in percent.",
        "- Exposure z: the design's `z_delegation` (conversations matched to O*NET tasks, "
        "aggregated to FF49), as given; it is not re-standardised per month or after drops.",
        "- log size: ln(average firm size) at the prior month-end, from the frozen "
        "`ff49_monthly` file (PAP §11 C-35).",
        "- log BE/ME: ln(\"Sum of BE / Sum of ME\") from the frozen `ff49_monthly` file, "
        "French's July-June timing: the row for year y (BE for fiscal y - 1 over ME at "
        "December y - 1) is used from July y to June y + 1 (PAP §11 C-38).",
        "- Momentum: the 12-2 cumulative return, prod over months t-12..t-2 of (1 + r/100) - 1, "
        "as a decimal, from the same value-weighted industry returns; missing unless all 11 "
        "returns are present.",
        "- A non-positive or missing size or BE/ME, a missing return or a missing exposure "
        "removes that industry from that month's regression (listed below).",
        "- Each month: OLS of the excess return on [1, z, log size, log BE/ME, momentum] across "
        "the complete industries. A month with n <= 5 complete industries is skipped and "
        "counted (PAP §11 C-38).",
        "- Each coefficient: the time-series mean of the monthly slopes, Newey-West SE with lag "
        "floor(4 (T/100)^(2/9)) (Bartlett kernel, no small-sample correction), p and 95% CI "
        "from the t distribution with T - 1 df.",
        "- Units: the slope on z is pp per month per 1 SD of exposure, with x 12 (annualised "
        "pp per 1 SD) beside it; the other slopes are pp per month per unit of the regressor "
        "(per unit of log size, of log BE/ME, and of the cumulative return as a decimal).",
        "- Windows: Design B, 2025-04 to 2026-08 month ends; Design A, 2022-12 to 2026-08 "
        "month ends (inclusive). A_r2 is formed from r2, the earliest release with task-level "
        "collaboration. A_pooled pools r2-r6; r3-r6 were published during and after the "
        "return window, so it is labelled look-ahead.",
        "- Every estimate is reported with its point value, CI and nominal p. No result is "
        "counted or starred; an interval that includes zero is reported in the same way as "
        "one that does not.",
    ]


_REASONS = (("ret_x", "return"), ("z", "exposure"), ("log_size", "size"),
            ("log_beme", "BE/ME"), ("mom", "momentum"))


def nonpositive(chars: pl.DataFrame, be_raw: pl.DataFrame, months: Sequence[date]
                ) -> dict[str, set[tuple[date, str]]]:
    """(month, industry) pairs whose size or BE/ME is present but <= 0, by panel column.

    `be_raw` is `data.beme(keep_nonpositive=True)`. Used only to label the drop list."""
    size = {(r["me_date"], r["ff49_short"]): r["avg_size"]
            for r in chars.select("me_date", "ff49_short", "avg_size").iter_rows(named=True)}
    bm = {(r["year"], r["ff49_short"]): r["beme"] for r in be_raw.iter_rows(named=True)}
    out: dict[str, set[tuple[date, str]]] = {"log_size": set(), "log_beme": set()}
    names = sorted({k[1] for k in size} | {k[1] for k in bm})
    for t in months:
        for nm in names:
            s = size.get((_prior_month_end(t), nm))
            if _ok(s) and s <= 0:
                out["log_size"].add((t, nm))
            b = bm.get((beme_year(t), nm))
            if _ok(b) and b <= 0:
                out["log_beme"].add((t, nm))
    return out


def _months_text(ms: list[date], total: int) -> str:
    return "all months" if len(ms) == total else ", ".join(f"{m:%Y-%m}" for m in ms)


def _drop_lines(panel: pl.DataFrame, nonpos: dict[str, set[tuple[date, str]]]) -> list[str]:
    """Industry-months missing a value, by industry and reason; a size or BE/ME that is present
    but <= 0 is labelled apart from an absent one."""
    items = []
    for nm in sorted(set(panel["ff49_short"].to_list())):
        g = panel.filter(pl.col("ff49_short") == nm).sort("date")
        parts = []
        for col, why in _REASONS:
            ms = g.filter(pl.col(col).is_null() | pl.col(col).is_nan())["date"].to_list()
            flagged = nonpos.get(col, set())
            le0 = [m for m in ms if (m, nm) in flagged]
            absent = [m for m in ms if (m, nm) not in flagged]
            if absent:
                parts.append(f"{why} ({_months_text(absent, g.height)})")
            if le0:
                parts.append(f"{why} <= 0 ({_months_text(le0, g.height)})")
        if parts:
            items.append(f"{nm}: {'; '.join(parts)}")
    return [f"  - {i}" for i in items] or ["  - none"]


def _table(res: dict) -> list[str]:
    lines = ["| regressor | mean slope (pp per month) | x 12 (annualised pp) | NW SE | 95% CI | "
             "p (nominal) | T | mean n | skipped months |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r, v in res.items():
        ann = f"{PERIODS * v['mean']:.3f}" if r == "z" else "-"
        lines.append(f"| {r} | {v['mean']:.3f} | {ann} | {v['se']:.3f} | "
                     f"[{v['ci95'][0]:.3f}, {v['ci95'][1]:.3f}] | {fmt_p(v['p'])} | {v['T']} | "
                     f"{v['n_mean']:.1f} | {v['skipped']} |")
    return lines


def _caveat_lines(run: list[tuple[str, str]], months_by: dict, same_b_a: bool) -> list[str]:
    designs = [d for d, _ in run]
    if not ("B" in designs and "A_r2" in designs):
        return []
    mb, ma = months_by["B"], months_by["A_r2"]
    if same_b_a and set(mb) <= set(ma):
        return [
            "- Design B and Design A_r2 exposures are numerically identical (both are formed "
            "from release r2; PAP §8.3 D19), so the B regressions are the A_r2 regressions, "
            f"with the same industries and exposure values, over a {len(mb)}-month sub-window "
            f"({mb[0]:%Y-%m} to {mb[-1]:%Y-%m}) of A_r2's {len(ma)} months. They are not "
            "independent evidence."]
    return ["- In this run the Design B and Design A_r2 exposures or windows differ, so the B "
            "regressions are not a sub-window of A_r2."]


def _md(run: list[tuple[str, str]], res_by: dict, panels: dict, skipped_by: dict,
        months_by: dict, zero: pl.DataFrame | None, nonpos: dict,
        caveats: list[str] | None = None) -> str:
    designs = [d for d, _ in run]
    lines = [HEADING, "", generated_line(GENERATOR), "",
             "Exploratory analysis (PAP §8.3). Every design here is exploratory; A_pooled is "
             "labelled look-ahead. Nothing here is a confirmatory test; the confirmatory "
             "H5/H5b decision in `docs/results/confirmatory_h5.md` stands as recorded.", ""]
    for d, _w in run:
        lines += [f"## Design {_label(d)}", "", *_table(res_by[d]), ""]
        ann = res_by[d]["z"]
        lines += [f"Slope on z: {ann['mean']:.3f} pp per month per 1 SD "
                  f"({PERIODS * ann['mean']:.3f} annualised pp per 1 SD), 95% CI "
                  f"[{ann['ci95'][0]:.3f}, {ann['ci95'][1]:.3f}] pp per month "
                  f"([{PERIODS * ann['ci95'][0]:.3f}, {PERIODS * ann['ci95'][1]:.3f}] "
                  f"annualised), p = {fmt_p(ann['p'])}, T = {ann['T']}, NW lag {ann['lag']}.", ""]
    lines += ["## Method", "", *_method_lines(), "",
              *(["## Caveats", "", *caveats, ""] if caveats else []),
              "## Exposure", "", *zero_assigned_bullets(designs, zero), "",
              "## Months", ""]
    for d, w in run:
        ms = months_by[d]
        sk = skipped_by[d]
        lines.append(f"- {_label(d)} (window {w}): {len(ms)} month ends, {ms[0]:%Y-%m} to "
                     f"{ms[-1]:%Y-%m}; skipped (n <= 5 complete industries): "
                     f"{', '.join(f'{m:%Y-%m}' for m in sk) or 'none'}")
    lines += ["", "## Industry-months missing a value", ""]
    for d, _ in run:
        lines += [f"- {_label(d)}:", *_drop_lines(panels[d], nonpos)]
    lines += ["", WORDING, ""]
    return "\n".join(lines)


def _months_by_key(months: dict[str, Sequence[date]] | None) -> dict[str, list[date]]:
    out: dict[str, list[date]] = {}
    for key in WINDOWS:
        full = window_months(key)
        given = sorted((months or {}).get(key, full))
        outside = [m for m in given if m not in set(full)]
        if outside:
            raise ValueError(f"months outside WINDOWS[{key!r}]: {outside}")
        if not given:
            raise ValueError(f"no months for window {key!r}")
        out[key] = given
    return out


def run_fm(out_dir: Path, months: dict[str, Sequence[date]] | None = None,
           expo: pl.DataFrame | None = None) -> pl.DataFrame:
    """Run every (design, window) in `RUNS` whose design `expo` holds; write
    `fama_macbeth.md` and `fama_macbeth.csv` (the returned frame) to `out_dir`.

    `months` maps a `WINDOWS` key to the month ends used (a key left out uses its whole
    window). `expo=None` uses `data.exposures()` and states the zero-assigned shares from
    `data.zero_assigned()`; a passed `expo` replaces it and the caller states its share."""
    out_dir = Path(out_dir)
    months_by_key = _months_by_key(months)
    zero = None
    if expo is None:
        expo = data.exposures()
        zero = data.zero_assigned()
    held = set(expo["design"].to_list())
    run = [(d, w) for d, w in RUNS if d in held]
    if not run:
        raise ValueError("expo holds none of the designs in RUNS")
    rows, res_by, panels, skipped_by, months_by = [], {}, {}, {}, {}
    for d, w in run:
        ms = months_by_key[w]
        panel = fm_panel(expo.filter(pl.col("design") == d), ms)
        res = fama_macbeth(panel)
        panels[d], res_by[d], months_by[d] = panel, res, ms
        skipped_by[d] = res[REGRESSORS[0]]["skipped_months"]
        for r, v in res.items():
            rows.append({"design": d, "window": w, "regressor": r, "mean": v["mean"],
                         "se": v["se"], "ci_lo": v["ci95"][0], "ci_hi": v["ci95"][1],
                         "p": v["p"], "T": v["T"], "n_mean": v["n_mean"],
                         "skipped": v["skipped"]})
    schema = {"design": pl.String, "window": pl.String, "regressor": pl.String,
              "mean": pl.Float64, "se": pl.Float64, "ci_lo": pl.Float64, "ci_hi": pl.Float64,
              "p": pl.Float64, "T": pl.Int64, "n_mean": pl.Float64, "skipped": pl.Int64}
    df = pl.DataFrame(rows, schema=schema).select(COLUMNS)
    all_months = sorted({m for ms in months_by.values() for m in ms})
    nonpos = nonpositive(data.characteristics(), data.beme(keep_nonpositive=True), all_months)
    caveats = _caveat_lines(run, months_by, identical_exposure(expo))
    text = _md(run, res_by, panels, skipped_by, months_by, zero, nonpos, caveats)
    check_text(text)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(df, out_dir / "fama_macbeth.csv")
    (out_dir / "fama_macbeth.md").write_text(text, encoding="utf-8")
    return df
