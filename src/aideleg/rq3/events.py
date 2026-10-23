"""D19 event studies and the Eisfeldt, Schubert & Zhang (2023) replication (PAP §8.3).
Exploratory throughout.

- `EVENTS` are the 14 dates under D19's objective rule; `EXCLUDED` gives the rule's exclusions
  with the PAP's reasons. Both are printed with D19's disclosure that the rule's exceptions were
  chosen with the source's list in view.
- Day 0 is the announcement date, or the next date present in both the industry and the factor
  files (`day_zero`); the move is reported (`event_days`).
- Abnormal return = industry decimal excess return minus its FF5 + UMD fit (intercept included),
  estimated by daily OLS over trading-day positions [-250, -21] relative to day 0. CAR_k is the
  sum of AR over days 0..k. An industry with any missing return in the estimation window or in
  the event window [0, max k] is dropped for that event, and the reason is reported.
- Each industry CAR is regressed on exposure across industries by OLS with an intercept and HC3
  SEs, nominal and single-test (PAP §11 C-33). Randomisation inference is not used: PAP §3.2
  documents its size. The HC3 CI and p use the normal reference, the statsmodels default (as in
  Plan 2's H4).
- Slopes are in pp of CAR per 1 SD of exposure. A_pooled is labelled look-ahead (D19).

Market data are read only through the guarded loaders in `aideleg.rq3.data`.
AEI data are conversations matched to O*NET tasks; nothing here speaks to the labour market.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import statsmodels.api as sm

from aideleg.results.common import WORDING, check_text, generated_line, write_csv
from aideleg.rq3 import data
from aideleg.rq3.report import zero_assigned_bullets

GENERATOR = "uv run python -m aideleg.rq3 events"
HEADING = "# Event studies (exploratory, PAP §8.3 D19)"
ESZ_HEADING = "# Eisfeldt, Schubert & Zhang (2023) replication (exploratory)"
FIG_NAME = "fig_rq3_event_slopes"

FACTORS = ("mkt_rf", "smb", "hml", "rmw", "cma", "umd")
ESTIMATION = (-250, -21)
HORIZONS = (5, 20)
ESZ_HORIZON = 9
ESZ_EVENT = "ChatGPT"
DESIGNS = ("A_r2", "A_pooled")
LOOK_AHEAD = "A_pooled"
COLUMNS = ["event", "day0", "horizon", "design", "regressors", "regressor", "b", "se", "ci_lo",
           "ci_hi", "p", "n"]


@dataclass(frozen=True)
class Event:
    name: str
    announced: date


EVENTS: tuple[Event, ...] = (
    Event("ChatGPT", date(2022, 11, 30)),
    Event("GPT-4", date(2023, 3, 14)),
    Event("PaLM 2", date(2023, 5, 10)),
    Event("Claude 2", date(2023, 7, 11)),
    Event("Claude 2.1", date(2023, 11, 21)),
    Event("Gemini 1.0", date(2023, 12, 6)),
    Event("Gemini 1.5", date(2024, 2, 15)),
    Event("Claude 3", date(2024, 3, 4)),
    Event("Claude 3.5", date(2024, 6, 20)),
    Event("OpenAI o1", date(2024, 9, 12)),
    Event("Gemini 2.0", date(2025, 2, 5)),
    Event("Claude 3.7", date(2025, 2, 24)),
    Event("GPT-4.5", date(2025, 2, 27)),
    Event("Gemini 2.5", date(2025, 3, 25)),
)

# PAP §8.3 D19, "Excluded by the rule" and the rule's "Flagship" term.
EXCLUDED: dict[str, str] = {
    "GPT-4o": "2024-05-13; not in the source's table",
    "o3-mini": "2025-01-31; not in the source's table",
    "DeepSeek-R1": "its developer is not one of the three named",
    "Gemma": "an open-weights small model, excepted from \"flagship\"",
    "Gemini Ultra": "a tier of a model family already listed (a tier of Gemini 1.0), excepted "
                    "from \"flagship\"",
}

# PAP §8.3 D19, verbatim.
DISCLOSURE = (
    "The rule's exceptions were chosen with the source's list in view: excluding Gemma and "
    "Gemini Ultra, adding ChatGPT by name, and accepting that GPT-4o is absent from the source "
    "were each decided after the source's rows, and therefore the resulting dates, had been "
    "seen. They are exploratory parameters, and are labelled as chosen with the list in view.")

RULE = [
    "The events are ChatGPT (2022-11-30), which the spec names (§5.4), and every flagship model "
    "announcement by OpenAI, Anthropic or Google's AI labs (listed as \"Google\" or \"Google "
    "DeepMind\") in a named source between 2022-11-30 and 2025-03-31 (PAP §8.3 D19, P7).",
    "- **Named source.** Wikipedia, \"List of large language models\", revision 1381207107 "
    "[facts §4].",
    "- **Flagship.** Every row of that source from those developers, except open-weights small "
    "models (Gemma) and a tier of a model family already listed (Gemini Ultra, a tier of Gemini "
    "1.0).",
    # Day and Trading days: PAP §8.3 D19, verbatim.
    "- **Day.** The source's date where it gives a day. Otherwise the developer's own "
    "announcement date in the source's month, verified in the facts file. Where the developer's "
    "page and the developer's own model identifier disagree on the day, the earlier date is "
    "used, so that the [0, +k] window contains the announcement either way. This applies only "
    "to Claude 3.5: the page shows 2024-06-21 and the identifier `claude-3-5-sonnet-20240620` "
    "gives 2024-06-20.",
    "- **Trading days.** Day 0 is the announcement date; if that is not a trading day, day 0 is "
    "the next trading day. Whether any date is an NYSE holiday is unverified for 2022–2025 "
    "[facts §4]. It is checked mechanically after the tag against the dates in the frozen "
    "files.",
    "- The mechanical check is the event-days table below: day 0 is the first date on or after "
    "the announcement present in both the industry and the factor files.",
    "- Gemini 2.0 uses the source's date, 2025-02-05; the first 2.0 Flash Experimental "
    "announcement, 2024-12-11, is not used.",
    "- Only model-release dates are used, never dates chosen from market reactions.",
]


def _trading_days(returns: pl.DataFrame, factors: pl.DataFrame) -> list[date]:
    return sorted(set(returns["date"].to_list()) & set(factors["date"].to_list()))


def day_zero(announced: date, trading_days: Sequence[date]) -> date:
    """The first date >= `announced` in `trading_days` (dates present in both daily files)."""
    later = [d for d in trading_days if d >= announced]
    if not later:
        raise ValueError(f"no trading day on or after {announced}")
    return min(later)


def _joined(returns: pl.DataFrame, factors: pl.DataFrame) -> pl.DataFrame:
    return returns.join(factors.select("date", *FACTORS, "rf"), on="date",
                        how="inner").sort("date")


def _positions(j: pl.DataFrame, day0: date, last: int) -> tuple[int, slice, slice]:
    days = j["date"].to_list()
    p0 = days.index(day_zero(day0, days))
    lo, hi = p0 + ESTIMATION[0], p0 + ESTIMATION[1]
    if lo < 0:
        raise ValueError(f"day 0 {days[p0]}: fewer than {-ESTIMATION[0]} trading days before it")
    if p0 + last >= len(days):
        raise ValueError(f"day 0 {days[p0]}: the event window [0, +{last}] runs past the data")
    est, win = slice(lo, hi + 1), slice(p0, p0 + last + 1)
    sub = pl.concat([j[est], j[win]])
    if sub.select(pl.max_horizontal(pl.col(list(FACTORS) + ["rf"]).is_null())).to_series().any():
        raise ValueError(f"missing factor values around day 0 {days[p0]}")
    return p0, est, win


def _xy(j: pl.DataFrame, rows: slice, names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    w = j[rows]
    X = np.column_stack([np.ones(w.height)] + [w[c].to_numpy() / 100 for c in FACTORS])
    rf = w["rf"].to_numpy() / 100
    Y = np.column_stack([w[n].cast(pl.Float64).fill_null(np.nan).to_numpy() / 100 - rf
                         for n in names])
    return X, Y


def fit_betas(returns: pl.DataFrame, factors: pl.DataFrame, day0: date, last: int = 0
              ) -> tuple[np.ndarray, list[str], int]:
    """FF5 + UMD coefficients (7 x industries, intercept first; NaN columns for an industry with
    a missing estimation return), the industry names, and the estimation row count (230)."""
    j = _joined(returns, factors)
    names = [c for c in returns.columns if c != "date"]
    _, est, _ = _positions(j, day0, last)
    X, Y = _xy(j, est, names)
    coef = np.full((X.shape[1], len(names)), np.nan)
    ok = ~np.isnan(Y).any(axis=0)
    if ok.any():
        coef[:, ok] = np.linalg.lstsq(X, Y[:, ok], rcond=None)[0]
    return coef, names, X.shape[0]


def event_cars(returns: pl.DataFrame, factors: pl.DataFrame, event: Event,
               horizons: Sequence[int]) -> pl.DataFrame:
    """`ff49_short`, `car_<k>` (decimal) per horizon, `dropped` ("estimation", "event" or
    null). Inputs are in percent, as the French loaders return them."""
    last = max(horizons)
    j = _joined(returns, factors)
    coef, names, _ = fit_betas(returns, factors, event.announced, last)
    _, _, win = _positions(j, event.announced, last)
    X, Y = _xy(j, win, names)
    ar = Y - X @ np.nan_to_num(coef)
    est_bad = np.isnan(coef).any(axis=0)
    win_bad = np.isnan(Y).any(axis=0)
    out: dict[str, list] = {"ff49_short": names}
    for k in horizons:
        out[f"car_{k}"] = [None if (est_bad[i] or win_bad[i]) else float(ar[:k + 1, i].sum())
                           for i in range(len(names))]
    out["dropped"] = ["estimation" if est_bad[i] else "event" if win_bad[i] else None
                      for i in range(len(names))]
    schema = {"ff49_short": pl.String, **{f"car_{k}": pl.Float64 for k in horizons},
              "dropped": pl.String}
    return pl.DataFrame(out, schema=schema)


def car_regression(car: np.ndarray, regressors: dict[str, np.ndarray]) -> dict:
    """OLS of `car` on [1, *regressors] with HC3 SEs (normal reference), dropping rows with a
    NaN. Per regressor: `b`, `se`, `ci95` (lo, hi), `p`; plus `n`. Units as the inputs."""
    y = np.asarray(car, dtype=float)
    cols = [np.asarray(v, dtype=float) for v in regressors.values()]
    ok = ~np.isnan(y)
    for c in cols:
        ok &= ~np.isnan(c)
    X = sm.add_constant(np.column_stack([c[ok] for c in cols]), has_constant="add")
    fit = sm.OLS(y[ok], X).fit(cov_type="HC3")
    ci = fit.conf_int(0.05)
    out: dict = {"n": int(ok.sum())}
    for i, name in enumerate(regressors, start=1):
        out[name] = {"b": float(fit.params[i]), "se": float(fit.bse[i]),
                     "ci95": (float(ci[i, 0]), float(ci[i, 1])), "p": float(fit.pvalues[i])}
    return out


def event_days(events: Sequence[Event], trading_days: Sequence[date]) -> pl.DataFrame:
    """`event, announced, day0, moved, overlaps`; `overlaps` lists the other events whose day 0
    lies in this event's [0, +max(HORIZONS)] trading days."""
    days = sorted(trading_days)
    pos = {d: i for i, d in enumerate(days)}
    d0 = [day_zero(e.announced, days) for e in events]
    span = max(HORIZONS)
    overlaps = [[o.name for o, od in zip(events, d0, strict=True)
                 if o.name != e.name and 0 <= pos[od] - pos[d] <= span]
                for e, d in zip(events, d0, strict=True)]
    return pl.DataFrame({"event": [e.name for e in events],
                         "announced": [e.announced for e in events], "day0": d0,
                         "moved": [d != e.announced for e, d in zip(events, d0, strict=True)],
                         "overlaps": overlaps},
                        schema={"event": pl.String, "announced": pl.Date, "day0": pl.Date,
                                "moved": pl.Boolean, "overlaps": pl.List(pl.String)})


def _rows(event: str, day0: date, horizon: int, design: str | None, res: dict,
          names: list[str]) -> list[dict]:
    return [{"event": event, "day0": day0, "horizon": horizon, "design": design,
             "regressors": "+".join(names), "regressor": nm, "b": 100 * res[nm]["b"],
             "se": 100 * res[nm]["se"], "ci_lo": 100 * res[nm]["ci95"][0],
             "ci_hi": 100 * res[nm]["ci95"][1], "p": res[nm]["p"], "n": res["n"]}
            for nm in names]


def _aligned(cars: pl.DataFrame, expo: pl.DataFrame, design: str) -> pl.DataFrame:
    ex = expo.filter(pl.col("design") == design).select("ff49_short", "z_delegation", "z_aioe")
    return cars.join(ex, on="ff49_short", how="left").sort("ff49_short")


def _np(s: pl.Series) -> np.ndarray:
    return s.cast(pl.Float64).fill_null(np.nan).to_numpy()


def _design_label(d: str | None) -> str:
    if d is None:
        return "none (z_aioe only)"
    return f"{d} (look-ahead)" if d == LOOK_AHEAD else d


def _fmt_row(r: dict) -> str:
    return (f"| {r['event']} | {r['day0']} | {r['horizon']} | {_design_label(r['design'])} | "
            f"{r['regressors']} | {r['regressor']} | {r['b']:.3f} | {r['se']:.3f} | "
            f"[{r['ci_lo']:.3f}, {r['ci_hi']:.3f}] | {r['p']:.4f} | {r['n']} |")


_TABLE_HEAD = ["| event | day 0 | horizon k | design | regressors | regressor | b (pp per 1 SD) "
               "| HC3 SE | 95% CI | p (nominal) | n |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]


def _method_lines(n_ind: int) -> list[str]:
    return [
        f"- Returns: FF49 daily value-weighted industry returns and FF5 + UMD daily factors, "
        f"read through the guarded loaders; {n_ind} industries. Excess return = industry return "
        "minus rf, in decimal.",
        f"- Estimation: daily OLS of excess return on [1, mkt_rf, smb, hml, rmw, cma, umd] over "
        f"trading-day positions [{ESTIMATION[0]}, {ESTIMATION[1]}] relative to day 0 "
        f"({ESTIMATION[1] - ESTIMATION[0] + 1} rows).",
        "- AR = excess return minus the fitted value, intercept included. CAR_k = sum of AR over "
        "days 0..k, in pp.",
        "- An industry with any missing return in the estimation window or in the event window "
        "[0, max k] is dropped for that event (listed below).",
        "- Cross-section: OLS of CAR_k on [1, exposure] across industries, HC3 SEs, 95% CI and p "
        "from the normal reference; nominal and single-test (PAP §11 C-33). Randomisation "
        "inference is not used: PAP §3.2 documents that it is oversized when industries with "
        "similar exposure co-move.",
        "- Slopes b, SEs and CIs are pp of CAR per 1 SD of exposure. Exposure is the Design A "
        "`z_delegation` (conversations matched to O*NET tasks, aggregated to FF49); it is not "
        "re-standardised after drops.",
        "- A_r2 is formed from r2, the earliest release with task-level collaboration. A_pooled "
        "pools r2-r6 (`claude_ai`, equal release weights); r3-r6 were published during and "
        "after the return window, so it is labelled look-ahead.",
        "- Every regression run is reported below with its point value, CI and nominal p. No "
        "result is counted or starred; an interval that includes zero is reported in the same "
        "way as one that does not.",
    ]


def _exposure_missing(expo: pl.DataFrame, names: list[str], design: str, col: str
                      ) -> list[str]:
    """Industries in `names` with no `col` value for `design` in `expo` (null or absent)."""
    ex = expo.filter(pl.col("design") == design).select("ff49_short", col)
    have = {r["ff49_short"] for r in ex.iter_rows(named=True) if r[col] is not None}
    return [n for n in names if n not in have]


def _exposure_lines(missing: dict[str, list[str]]) -> list[str]:
    return [f"- Exposure missing ({key}): "
            f"{', '.join(f'{n} (exposure)' for n in v) or 'none'}; excluded from those "
            "regressions' n" for key, v in missing.items()]


def _dropped_lines(drops: dict[str, pl.DataFrame]) -> list[str]:
    out = []
    for ev, cars in drops.items():
        d = cars.filter(pl.col("dropped").is_not_null())
        items = ", ".join(f"{r['ff49_short']} ({r['dropped']})" for r in d.iter_rows(named=True))
        out.append(f"- {ev}: {items or 'none'}")
    return out


def _event_study_md(df: pl.DataFrame, ed: pl.DataFrame, events: Sequence[Event],
                    designs: Sequence[str], zero: pl.DataFrame | None,
                    drops: dict[str, pl.DataFrame], n_ind: int,
                    missing: dict[str, list[str]]) -> str:
    is_d19 = tuple(events) == EVENTS
    ev_title = (f"The {len(EVENTS)} dates under the rule" if is_d19
                else f"Events in this run ({len(events)}; not the D19 list)")
    days_rows = [f"| {r['event']} | {r['announced']} | {r['day0']} | "
                 f"{'yes' if r['moved'] else 'no'} | {', '.join(r['overlaps']) or '-'} |"
                 for r in ed.iter_rows(named=True)]
    main = df.filter(pl.col("horizon").is_in(list(HORIZONS)))
    lines = [
        HEADING, "", generated_line(GENERATOR), "",
        "Exploratory analysis (PAP §8.3, D19). Nothing here is a confirmatory test; the "
        "confirmatory H5/H5b decision in `docs/results/confirmatory_h5.md` stands as recorded.",
        "", "## The event rule (D19)", "", *RULE, "",
        f"## {ev_title}", "", "| event | announced |", "|---|---|",
        *[f"| {e.name} | {e.announced} |" for e in events], "",
        "## Excluded by the rule", "",
        *[f"- {k}: {v}" for k, v in EXCLUDED.items()], "",
        "## Disclosure (D19)", "", DISCLOSURE, "",
        "## Event days", "",
        "Day 0 is the first date on or after the announcement present in both the industry and "
        f"the factor files. `overlaps` lists the other events whose day 0 lies in this event's "
        f"[0, +{max(HORIZONS)}] trading days. Also in `event_days.csv`.", "",
        "| event | announced | day 0 | moved | overlaps |", "|---|---|---|---|---|",
        *days_rows, "",
        "## Method", "", *_method_lines(n_ind), "",
        "## Exposure", "", *zero_assigned_bullets(designs, zero), "",
        f"## Slopes, horizons {' and '.join(str(h) for h in HORIZONS)}", "",
        "Per event and horizon: CAR on A_r2 `z_delegation`, then CAR on A_pooled "
        "`z_delegation` (look-ahead), each alone. Full precision in `event_study.csv`.", "",
        *_TABLE_HEAD, *[_fmt_row(r) for r in main.iter_rows(named=True)], "",
        "## Dropped industries", "",
        "For a missing return (per event; reason in brackets):", "", *_dropped_lines(drops), "",
        "For a missing exposure value (every event):", "", *_exposure_lines(missing), "",
        WORDING, "",
    ]
    return "\n".join(lines)


def _esz_md(df: pl.DataFrame, day0: date, designs: Sequence[str], zero: pl.DataFrame | None,
            cars: pl.DataFrame, missing: dict[str, list[str]]) -> str:
    esz = df.filter(pl.col("horizon") == ESZ_HORIZON)
    alone = esz.filter(pl.col("design").is_null()).row(0, named=True)
    sign = "positive" if alone["b"] > 0 else "negative" if alone["b"] < 0 else "zero"
    race = esz.filter(pl.col("design").is_not_null())
    lines = [
        ESZ_HEADING, "", generated_line(GENERATOR), "",
        "Exploratory comparison with Eisfeldt, Schubert & Zhang (2023) (PAP §8.3, D19): the sign "
        f"of the CAR-`z_aioe` slope over [0, +{ESZ_HORIZON}] around the ChatGPT release "
        f"(announced 2022-11-30, day 0 {day0}), before `z_delegation` is added. FF49 industries "
        "and FF5 + UMD abnormal returns as in `event_study.md`; this is not their firm-level "
        "design.", "",
        "## Method", "",
        f"- CAR over [0, +{ESZ_HORIZON}] as in `event_study.md` (estimation [{ESTIMATION[0]}, "
        f"{ESTIMATION[1]}], FF5 + UMD, intercept included).",
        "- OLS across industries with an intercept and HC3 SEs, normal reference, nominal and "
        "single-test (PAP §11 C-33); no randomisation inference (PAP §3.2).",
        "- Slopes are pp of CAR per 1 SD of the regressor. A_pooled is labelled look-ahead.", "",
        "## Exposure", "", *zero_assigned_bullets(designs, zero), "",
        "## Step 1: CAR on `z_aioe` alone", "",
        f"The `z_aioe` slope is {sign}: b = {alone['b']:.3f} pp per 1 SD (95% CI "
        f"[{alone['ci_lo']:.3f}, {alone['ci_hi']:.3f}], p = {alone['p']:.4f}, n = "
        f"{alone['n']}).", "",
        *_TABLE_HEAD, _fmt_row(alone), "",
        "## Step 2: horse race, `z_aioe` with `z_delegation`", "",
        "A_r2 first, then A_pooled (look-ahead).", "",
        *_TABLE_HEAD, *[_fmt_row(r) for r in race.iter_rows(named=True)], "",
        "## Dropped industries", "",
        "For a missing return (reason in brackets):", "", *_dropped_lines({ESZ_EVENT: cars}), "",
        "For a missing exposure value:", "", *_exposure_lines(missing), "",
        WORDING, "",
    ]
    return "\n".join(lines)


def _figure(df: pl.DataFrame, events: Sequence[Event]):
    import matplotlib.pyplot as plt

    from aideleg.figures import FIGSIZE, PALETTE, apply_style

    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["double"])
    sub = df.filter((pl.col("design") == "A_r2") & pl.col("horizon").is_in(list(HORIZONS)))
    names = [e.name for e in events]
    x = np.arange(len(names))
    for i, (h, color) in enumerate(zip(HORIZONS, (PALETTE[5], PALETTE[6]), strict=False)):
        s = sub.filter(pl.col("horizon") == h)
        by = {r["event"]: r for r in s.iter_rows(named=True)}
        xs = [x[k] + (i - 0.5) * 0.3 for k, n in enumerate(names) if n in by]
        rs = [by[n] for n in names if n in by]
        b = np.array([r["b"] for r in rs])
        lo = b - np.array([r["ci_lo"] for r in rs])
        hi = np.array([r["ci_hi"] for r in rs]) - b
        ax.errorbar(xs, b, yerr=[lo, hi], fmt="o", ms=3, capsize=2, color=color, lw=0.8,
                    label=f"CAR [0, +{h}]")
    ax.axhline(0.0, color="#777777", lw=0.6)
    ax.set_xticks(x, names, rotation=45, ha="right")
    ax.set_ylabel("slope, pp of CAR per 1 SD of A_r2 z_delegation")
    ax.set_title("Event-study slopes on A_r2 z_delegation, 95% HC3 CIs (exploratory)")
    ax.legend(frameon=False)
    fig.tight_layout()
    return fig


def run_events(out_dir: Path, events: Sequence[Event] = EVENTS,
               expo: pl.DataFrame | None = None, *, fig_dir: Path | None = None
               ) -> pl.DataFrame:
    """Run every event x horizon regression and, when `ChatGPT` is among `events`, the Eisfeldt
    et al. replication. Writes `event_study.md`, `event_study.csv` (the returned frame),
    `event_days.csv` and, with the replication, `eisfeldt_replication.md` to `out_dir`; the
    figure `fig_rq3_event_slopes` goes to `fig_dir` when one is given.

    `expo=None` uses `data.exposures()` and states the zero-assigned shares from
    `data.zero_assigned()`. A passed `expo` replaces it; the caller states its share."""
    out_dir = Path(out_dir)
    events = tuple(events)
    returns, factors = data.daily("VW")
    zero = None
    if expo is None:
        expo = data.exposures()
        zero = data.zero_assigned()
    designs = [d for d in DESIGNS if d in set(expo["design"].to_list())]
    if not designs:
        raise ValueError(f"expo holds none of the Design A labels {DESIGNS}")
    tdays = _trading_days(returns, factors)
    ed = event_days(events, tdays)
    d0 = dict(zip(ed["event"].to_list(), ed["day0"].to_list(), strict=True))
    rows: list[dict] = []
    drops: dict[str, pl.DataFrame] = {}
    esz_cars = None
    for ev in events:
        hs = tuple(HORIZONS) + ((ESZ_HORIZON,) if ev.name == ESZ_EVENT else ())
        cars = event_cars(returns, factors, ev, sorted(hs))
        drops[ev.name] = cars
        for h in HORIZONS:
            for d in designs:
                al = _aligned(cars, expo, d)
                res = car_regression(_np(al[f"car_{h}"]), {"z_delegation": _np(al["z_delegation"])})
                rows += _rows(ev.name, d0[ev.name], h, d, res, ["z_delegation"])
        if ev.name == ESZ_EVENT:
            esz_cars = cars
            al = _aligned(cars, expo, designs[0])
            car9 = _np(al[f"car_{ESZ_HORIZON}"])
            res = car_regression(car9, {"z_aioe": _np(al["z_aioe"])})
            rows += _rows(ev.name, d0[ev.name], ESZ_HORIZON, None, res, ["z_aioe"])
            for d in designs:
                al = _aligned(cars, expo, d)
                res = car_regression(_np(al[f"car_{ESZ_HORIZON}"]),
                                     {"z_aioe": _np(al["z_aioe"]),
                                      "z_delegation": _np(al["z_delegation"])})
                rows += _rows(ev.name, d0[ev.name], ESZ_HORIZON, d, res,
                              ["z_aioe", "z_delegation"])
    schema = {"event": pl.String, "day0": pl.Date, "horizon": pl.Int64, "design": pl.String,
              "regressors": pl.String, "regressor": pl.String, "b": pl.Float64,
              "se": pl.Float64, "ci_lo": pl.Float64, "ci_hi": pl.Float64, "p": pl.Float64,
              "n": pl.Int64}
    df = pl.DataFrame(rows, schema=schema).select(COLUMNS)
    ind = [c for c in returns.columns if c != "date"]
    n_ind = len(ind)
    missing = {f"z_delegation, Design {d}": _exposure_missing(expo, ind, d, "z_delegation")
               for d in designs}
    text = _event_study_md(df, ed, events, designs, zero, drops, n_ind, missing)
    check_text(text)
    esz_text = None
    if esz_cars is not None:
        esz_missing = {f"z_aioe, Design {designs[0]} rows":
                       _exposure_missing(expo, ind, designs[0], "z_aioe"), **missing}
        esz_text = _esz_md(df, d0[ESZ_EVENT], designs, zero, esz_cars, esz_missing)
        check_text(esz_text)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(df, out_dir / "event_study.csv")
    write_csv(ed.with_columns(pl.col("overlaps").list.join("; ")), out_dir / "event_days.csv")
    (out_dir / "event_study.md").write_text(text, encoding="utf-8")
    if esz_text is not None:
        (out_dir / "eisfeldt_replication.md").write_text(esz_text, encoding="utf-8")
    if fig_dir is not None:
        from aideleg.figures import save_figure

        save_figure(_figure(df, events), FIG_NAME, out_dir=Path(fig_dir))
    return df
