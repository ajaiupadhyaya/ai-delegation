"""The PAP §8.2 robustness row runners (Plan 4). Each `run_R<nn>()` writes
`docs/results/robustness/R<nn>.csv` and `.md` through `report.write_row` and returns their paths.

Exposure-construction rows (Task 7): R1, R2, R3, R11, R14, R15, R17, R20, R33. Each rebuilds
the Design B exposure under one fixed `ExposureSpec` and writes up to two parts:

- `market`: H5 and H5b through `market.market_variant` on `ff49_vw`, with s, b-bar and q
  recomputed for the variant's exposure vector on the 378 pre-seal windows (PAP §3.3, §8.1, D21);
- `rq2`: Plan 2's could-vs-does Spearman table (`upstream.rq2_correlations`) of the variant
  indices against the variant benchmarks, with Plan 2's Design B bootstrap draws (C-68).

Returns, sample and inference rows (Task 8): R5, R7, R10 (market parts), R18, R19, R21, R34,
R35. Each runs on the primary Design B exposure (`ExposureSpec()`) and varies one market input:
the return set, the industries, the exposure column, the null scale, the history start, or (R35)
the statistic.

New-data rows (Task 9): R6 rebuilds the exposure on the FF30 / FF48 industries and runs on the
`ff30_vw` / `ff48_vw` files (parts `ff30`, `ff48`); R32 is strict real-time Design B (OEWS May
2023 weights, O*NET 29.2 task statements) on `ff49_vw`. Market parts only.

Design A and event rows (Task 10): R4 (`1p_api` A_pooled), R8 (calendar 2023 excluded), R9
(placebo event dates) and R16 (r6 task-allocated basis). Design A is analysed by Plan 3's
terciles, Fama–MacBeth and event slopes, so each Design A part runs those runners
(`upstream.run_terciles`, `run_fm`, `run_events`) on the variant exposure, with `out_dir` under
the untracked `WORK_DIR` and no figure directory. All are exploratory.

H1/H3 rows (Task 11): R10 (RQ1 parts `h1_lb`, `h1_ub`, `h3_lb`, `h3_ub`, written beside the
committed market parts, which are carried verbatim and never re-run), R23 (part `h1`), R24,
R26, R27, R31 and R38, each through Plan 2's `build_task_rows` and `estimate_h1` /
`estimate_h3` (via the adapter) after `guards.require_rq1_run_committed()`.

Every record is reported as robustness; no row changes a confirmatory decision (PAP §8.1).
AEI data are conversations matched to O*NET tasks.
"""

import calendar
import csv
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from aideleg import confirm_h5, power
from aideleg.occupations import SUPPRESSION
from aideleg.robustness import (
    guards,
    market,
    registry,
    report,
    returns,
    rq1,
    studentised,
    upstream,
)
from aideleg.robustness.exposure_variants import (
    ZERO_ASSIGNED_NOTE,
    ExposureSpec,
    variant_exposure,
    zero_assigned_share,
)
from aideleg.robustness.market import market_variant
from aideleg.robustness.upstream import AEI_COLS, BENCH_COLS, Event, rq2_correlations

OUT_DIR: Path = report.OUT_DIR
RETURN_SET = "ff49_vw"
LOOK_AHEAD = (
    "Look-ahead (PAP §8.2 R1): the May 2025 weights were published after the formation date "
    "and during the return window."
)
# C-71: the frozen majority rule assigns no NAICS code to these three FF49 industries
R20_ABSENT: dict[int, str] = {26: "Guns", 27: "Gold", 40: "Boxes"}
HEADLINE = "z_eloundou"  # PAP D8: the Eloundou human beta is the headline benchmark
R17_HEADLINE = "z_eloundou_gpt4"  # R17: the GPT-4 beta as headline (D8 alternative)
# rank order of the benchmarks in an RQ2 part, the headline first (as Plan 2's RANK_BENCHMARKS)
_BENCH_ORDER = {
    HEADLINE: (HEADLINE, R17_HEADLINE, "z_aioe"),
    R17_HEADLINE: (R17_HEADLINE, HEADLINE, "z_aioe"),
}

_MARKET_NOTE = (
    f"Market part: H5 and H5b on {RETURN_SET} with s, b̄ and q recomputed for this exposure "
    "vector on the same 378 pre-seal windows, the t₂₁ rule and the D21 null b₀ = b̄ "
    "(PAP §3.3, §8.1); z is the variant's own and is not re-standardised after a drop."
)
_RQ2_NOTE = (
    "RQ2 part: Spearman correlations of the variant AEI indices with the variant benchmarks; "
    "the intervals are 2.5/97.5 percentile industry-bootstrap intervals on Plan 2's Design B "
    'draw set `bootstrap_indices(n)["B"]` (PAP §11 C-68). RQ2 is descriptive.'
)
_BENCH_REAGG = (
    "Benchmarks: AIOE and Eloundou are re-aggregated with the variant's matrix, crosswalk and "
    "industry set, so both sides of H5b use the same weights (PAP §11 C-65)."
)
_BENCH_PRIMARY = (
    "Benchmarks: AIOE and Eloundou stay at their primary values, because this occupation-level "
    "variant changes neither the matrix nor the crosswalk (PAP §11 C-65)."
)


@dataclass(frozen=True)
class ExposureRow:
    row_id: str
    spec: ExposureSpec
    parts: tuple[str, ...]
    label: str
    notes: tuple[str, ...]
    market_hyps: tuple[str, ...] = ("H5", "H5b")
    headline: str = HEADLINE


EXPOSURE_ROWS: dict[str, ExposureRow] = {
    r.row_id: r
    for r in (
        ExposureRow(
            "R1",
            ExposureSpec(oews_year=2025),
            ("market", "rq2"),
            "robustness; look-ahead",
            (
                "OEWS May 2025 weights (industry matrix and national shares) in place of May "
                "2024 (PAP §8.2 R1).",
                LOOK_AHEAD,
                _BENCH_REAGG,
            ),
        ),
        ExposureRow(
            "R2",
            ExposureSpec(weights="wage_bill"),
            ("market", "rq2"),
            "robustness",
            (
                "Wage-bill weights (OEWS employment × mean wage) in place of employment weights "
                "(PAP §8.2 R2). A_MEAN `#` is set to the May 2024 top-code $239,200 and `*`/`**` "
                "give a null wage bill left out of the shares; the U_o denominators stay "
                "national employment shares (PAP §11 C-66).",
                "The wage bill replaces employment in both industry weights (the occupation "
                "shares within each OEWS NAICS code and the code weights that combine codes "
                "into an FF49 industry), so w_oj is o's share of industry j's wage bill; "
                "emp_covered_share is wage-bill weighted (PAP §11 C-72).",
                _BENCH_REAGG,
            ),
        ),
        ExposureRow(
            "R3",
            ExposureSpec(unmatched="drop"),
            ("market", "rq2"),
            "robustness",
            (
                'Occupations with no AEI match are dropped (`unmatched="drop"`) instead of '
                "assigned zero usage (PAP D3 alternative, §8.2 R3).",
                _BENCH_PRIMARY,
            ),
        ),
        ExposureRow(
            "R11",
            ExposureSpec(allocation="employment"),
            ("market", "rq2"),
            "robustness",
            (
                "Employment-weighted task allocation in place of the equal split (PAP D4 "
                "alternative, §8.2 R11): a task's usage goes to its candidate occupations in "
                "proportion to their national OEWS employment.",
                "PAP D4: this makes U equal across occupations sharing a task by construction, "
                "so it removes rather than tests the within-group dispersion.",
                _BENCH_PRIMARY,
            ),
        ),
        ExposureRow(
            "R14",
            ExposureSpec(aioe_crosswalk="bls"),
            ("market", "rq2"),
            "robustness",
            (
                "AIOE through the BLS SOC 2010→2018 crosswalk in place of the O*NET-detail "
                "union (PAP D6 alternative, §8.2 R14). The row applies to H5b and RQ2: H5 does "
                "not use AIOE, so the market part reports H5b only.",
                "AIOE's 19-1020 (not a SOC 2010 detailed code, absent from the BLS crosswalk) "
                "is mapped by its O*NET-SOC 2010→2019 successor 19-1029; every other AIOE code "
                "uses the BLS crosswalk (PAP §11 C-73).",
                "Benchmarks: AIOE itself is replaced; Eloundou and the AEI indices keep the "
                "primary matrix and crosswalk (PAP §11 C-65).",
            ),
            market_hyps=("H5b",),
        ),
        ExposureRow(
            "R15",
            ExposureSpec(hq="redistribute"),
            ("market", "rq2"),
            "robustness",
            (
                'NAICS 5511 redistributed (`hq="redistribute"`, PAP D7 alternative, §8.2 R15).',
                "Identical to the primary by construction (PAP §11 C-70): 5511's occupation mix "
                "is added to every FF49 industry with the same fraction of its mapped "
                "employment, an affine map of each industry index, so the standardised indices, "
                "every Spearman rank and every H5, H5b and RQ2 estimate equal the primary's; "
                "only coverage and index levels change. The row is still run and reported "
                "(PAP §8.1).",
                _BENCH_REAGG,
            ),
        ),
        ExposureRow(
            "R17",
            ExposureSpec(),
            ("rq2",),
            "robustness; descriptive",
            (
                "Primary Design B exposure and benchmarks; the RQ2 table is ordered with the "
                "Eloundou GPT-4 β (`z_eloundou_gpt4`) as headline (PAP D8 alternative, §8.2 "
                "R17). Both betas are always shown, so this is a labelling choice (PAP D8).",
            ),
            headline=R17_HEADLINE,
        ),
        ExposureRow(
            "R20",
            ExposureSpec(crosswalk="majority"),
            ("market", "rq2"),
            "robustness",
            (
                "NAICS→FF49 crosswalk in `majority` mode instead of `split` (PAP §8.2 R20).",
                "The majority rule assigns no NAICS code to Guns (26), Gold (27) or Boxes "
                "(40): the row reports on the 46 industries it assigns, with z standardised "
                "over those 46; the market part removes the three from the window and from the "
                "378-window history before the null scales are computed (PAP §11 C-71).",
                _BENCH_REAGG,
            ),
        ),
        ExposureRow(
            "R33",
            ExposureSpec(crosswalk="emp_weighted"),
            ("market", "rq2"),
            "robustness",
            (
                "Employment-weighted NAICS→SIC crosswalk from OEWS `nat5d_6d` (PAP D23, §8.2 "
                "R33). Children without published employment share the residual "
                "max(E₄ − Σ published, 0) equally; with no published child, the primary equal "
                "split (PAP §11 C-67).",
                _BENCH_REAGG,
            ),
        ),
    )
}


def describe_spec(spec: ExposureSpec) -> str:
    """The spec's non-default options, e.g. `ExposureSpec(oews_year=2025)`."""
    base = ExposureSpec()
    diff = [
        f"{f.name}={getattr(spec, f.name)!r}"
        for f in fields(spec)
        if getattr(spec, f.name) != getattr(base, f.name)
    ]
    return f"ExposureSpec({', '.join(diff)})"


def _market_frame(row: ExposureRow, expo: pl.DataFrame) -> tuple[pl.DataFrame, tuple[str, ...]]:
    """The market runner's exposure frame (`industry` = return column names) and drop list.
    R20's three unassigned industries are padded as null rows and dropped (C-71)."""
    frame = expo.select(pl.col("industry_short").alias("industry"), "z_delegation", "z_aioe")
    if row.spec.crosswalk != "majority":
        return frame, ()
    present = set(expo["industry"].to_list())
    absent = {i: n for i, n in R20_ABSENT.items() if i not in present}
    if absent != R20_ABSENT or expo.height != 49 - len(R20_ABSENT):
        raise ValueError(
            f"{row.row_id}: expected the majority crosswalk to leave out exactly "
            f"{R20_ABSENT} (C-71); {expo.height} industries, absent {absent}"
        )
    pad = pl.DataFrame(
        {
            "industry": list(R20_ABSENT.values()),
            "z_delegation": [None] * len(R20_ABSENT),
            "z_aioe": [None] * len(R20_ABSENT),
        },
        schema=frame.schema,
    )
    return pl.concat([frame, pad]), tuple(R20_ABSENT.values())


def _market_records(row: ExposureRow, expo: pl.DataFrame, desc: str) -> list[dict]:
    frame, drop = _market_frame(row, expo)
    recs = market_variant(row.row_id, "market", frame, rs=RETURN_SET, drop=drop, label=row.label)
    out = []
    for r in recs:
        if r["applies_to"] in row.market_hyps:
            out.append(r | {"variant": f"{desc}; {r['variant']}"})
    return out


def _rq2_records(row: ExposureRow, expo: pl.DataFrame, desc: str) -> list[dict]:
    ex = expo.select(pl.col("industry").alias("ff49"), *AEI_COLS)
    bench = expo.select(pl.col("industry").alias("ff49"), *BENCH_COLS)
    tab = rq2_correlations(ex, bench)
    present = set(expo["industry"].to_list())
    missing = [n for i, n in R20_ABSENT.items() if i not in present]
    order = {b: k for k, b in enumerate(_BENCH_ORDER[row.headline])}
    aei_order = {a: k for k, a in enumerate(AEI_COLS)}
    recs = sorted(
        tab.iter_rows(named=True), key=lambda t: (order[t["benchmark"]], aei_order[t["aei"]])
    )
    out = []
    for t in recs:
        # the .md table has no estimand column: the pair is named in the record's note
        note = f"{t['aei']} vs {t['benchmark']}; {t['n_draws_used']} bootstrap draws used"
        if t["benchmark"] == row.headline:
            tag = "R17" if row.headline == R17_HEADLINE else "D8"
            note = f"{note}; headline benchmark ({tag})"
        rec = {
            "row_id": row.row_id,
            "part": "rq2",
            "variant": f"{desc}; RQ2 headline {row.headline}",
            "applies_to": "RQ2",
            "label": row.label,
            "estimand": f"spearman {t['benchmark']} vs {t['aei']}",
            "unit": report.RHO_UNIT,
            "estimate": t["spearman"],
            "scale": None,
            "ci_lo": t["ci_low"],
            "ci_hi": t["ci_high"],
            "stat": None,
            "p": None,
            "null": None,
            "crit_0025": None,
            "crit_005": None,
            "n": t["n"],
            "n_dropped": len(missing),
            "dropped": ", ".join(missing),
            "note": note,
        }
        report.check_record(rec)
        out.append(rec)
    return out


def run_exposure_row(row_id: str, *, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Build the row's variant exposure, run its parts and write `R<nn>.csv` / `.md`."""
    row = EXPOSURE_ROWS[row_id]
    desc = describe_spec(row.spec)
    expo = variant_exposure(row.spec)
    records: list[dict] = []
    if "market" in row.parts:
        records += _market_records(row, expo, desc)
    if "rq2" in row.parts:
        records += _rq2_records(row, expo, desc)
    notes = [
        f"Variant: {desc}; every other construction choice is the primary Design B one.",
        *row.notes,
        ZERO_ASSIGNED_NOTE.format(zero_assigned_share(row.spec)),
    ]
    if "market" in row.parts:
        notes.append(_MARKET_NOTE)
    notes.append(_RQ2_NOTE)
    return report.write_row(row_id, records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


def _runner(row_id: str) -> Callable[..., tuple[Path, Path]]:
    def run(*, out_dir: Path | None = None) -> tuple[Path, Path]:
        return run_exposure_row(row_id, out_dir=out_dir)

    run.__name__ = f"run_{registry.output_stem(row_id)}"
    run.__doc__ = f"PAP §8.2 {row_id}: {describe_spec(EXPOSURE_ROWS[row_id].spec)}."
    return run


run_R01 = _runner("R1")
run_R02 = _runner("R2")
run_R03 = _runner("R3")
run_R11 = _runner("R11")
run_R14 = _runner("R14")
run_R15 = _runner("R15")
run_R17 = _runner("R17")
run_R20 = _runner("R20")
run_R33 = _runner("R33")

# --- Task 8: returns, sample and inference rows on the primary Design B exposure ----------

_PRIMARY = ExposureSpec()
_TECH = ("Hardw", "Softw", "Chips")
_RMS_Q = (
    "q is recomputed with the RMS s: q = the 0.975 / 0.95 quantiles of |b − b̄|/s with this s "
    "(PAP §8.1: s, b̄ and q recomputed; Plan 4 Task 4 Step 3 rule), and the critical is "
    "max(t₂₁, q); q moves a critical only where it exceeds t₂₁ ({t25} / {t5}), so the c_0.025 "
    "and c_0.05 columns show the criticals used."
)


@dataclass(frozen=True)
class MarketRow:
    row_id: str
    parts: tuple[tuple[str, dict], ...]
    notes: tuple[str, ...]
    label: str = "robustness"
    extra: Callable[[list[dict], pl.DataFrame], list[str]] | None = field(
        default=None, compare=False
    )


def history_drops(rs: str, names: list[str], first: date) -> tuple[int, int, list[str]]:
    """(industry-window drops, windows with a drop, industries dropped somewhere) in the
    pre-seal history from `first`: an industry with any missing return in a window has no
    alpha there and is left out of that window's slope (`power._cross_section`)."""
    miss = np.isnan(market.history(rs, names, first=first))
    return (
        int(miss.sum()),
        int(miss.any(axis=1).sum()),
        sorted({names[j] for j in np.where(miss.any(axis=0))[0]}),
    )


def _r34_extra(records: list[dict], frame: pl.DataFrame) -> list[str]:
    out = []
    for part, kw in MARKET_ROWS["R34"].parts:
        rec = next(r for r in records if r["part"] == part)
        dropped = set(filter(None, (rec["dropped"] or "").split(", ")))
        names = [n for n in frame["industry"].to_list() if n not in dropped]
        n, w, who = history_drops(kw.get("rs", RETURN_SET), names, kw["first"])
        nw = len(power.historical_windows(kw["first"]))
        out.append(
            f"{part} ({kw['first']:%Y-%m}, {nw} windows): {n} industry-window drops in {w} "
            f"windows ({', '.join(who) or 'none'})."
        )
    return out


MARKET_ROWS: dict[str, MarketRow] = {
    r.row_id: r
    for r in (
        MarketRow(
            "R5",
            (("market", {"rs": "ff49_ew"}),),
            (
                "Equal-weighted FF49 daily returns in place of value-weighted, in the "
                "confirmatory window and in the 378-window history (PAP §8.2 R5).",
            ),
        ),
        MarketRow(
            "R7",
            (("market", {"drop": _TECH}),),
            (
                "Technology industries Hardw, Softw and Chips dropped from the window and the "
                "history (PAP §8.2 R7).",
                "[default] z not re-standardised after the drop, as for R13 (PAP §11 C-63).",
            ),
        ),
        MarketRow(
            "R10",
            (
                ("market_lb", {"z_col": "z_delegation_lb"}),
                ("market_ub", {"z_col": "z_delegation_ub"}),
            ),
            (
                "Market parts of R10: the D1 suppression bounds `z_delegation_lb` and "
                "`z_delegation_ub` (built from `automation_pct_lb` / `_ub`) in place of "
                "`z_delegation`, for H5 and H5b (PAP §8.2 R10, D1). The H1 and H3 parts of R10 "
                "are RQ1 rows (PAP §11 C-57).",
            ),
        ),
        MarketRow(
            "R18",
            (("market", {"scale": "nonoverlap_max"}),),
            (
                "s = the largest sd of the 17 non-overlapping start offsets; b̄ stays the "
                "378-window mean; q is recomputed with the new s (PAP §3.3, §8.2 R18; §11 "
                "C-64).",
            ),
        ),
        MarketRow(
            "R19",
            (("market", {"scale": "rms"}),),
            (
                "s = the root mean square of the 378 historical slopes around the null value "
                "b̄, sqrt(mean((b − b̄)²)) (PAP §3.3, §8.2 R19).",
                _RMS_Q.format(
                    t25=report.fmt_crit(power.t_crit(0.025)),
                    t5=report.fmt_crit(power.t_crit(0.05)),
                ),
            ),
        ),
        MarketRow(
            "R21",
            (
                ("usage", {"z_col": "z_usage"}),
                ("augmentation", {"z_col": "z_augmentation"}),
            ),
            (
                "`z_usage` and `z_augmentation` in place of `z_delegation` (PAP §8.2 R21), each "
                "with its own s, b̄ and q.",
                "No error control: R21 carries no error control across its parts or across "
                "rows (PAP §8.1).",
            ),
            label="robustness; no error control",
        ),
        MarketRow(
            "R34",
            (
                ("from_1969", {"first": date(1969, 7, 1)}),
                ("from_1963", {"first": date(1963, 7, 1)}),
            ),
            (
                "Null scale, b̄ and criticals from overlapping 17-month windows starting "
                "1969-07 (the first month with all 49 industries) and 1963-07 (the first daily "
                "FF5 month), ending by 2022-11-29 (PAP §3.3, §7, §8.2 R34).",
                "1963-07 rows are not like-for-like: industries missing in early windows. An "
                "industry with any missing return in a historical window has no alpha there and "
                "is left out of that window's slope only (the power analysis rule, PAP §7); z is "
                "not re-standardised. The drop counts below are computed from the history.",
            ),
            extra=_r34_extra,
        ),
    )
}

_MARKET_ROW_NOTE = (
    "Exposure: the primary Design B vector (`ExposureSpec()`). H5 and H5b with s, b̄ and q "
    "recomputed for this row by the pre-seal procedure (the same 378 windows unless the row "
    "says otherwise, the t₂₁ rule and the D21 null b₀ = b̄; PAP §3.3, §8.1); industries with a "
    "missing return in the confirmatory window are dropped and z is not re-standardised. The "
    "secondary b = 0 statistic is in each record's note."
)


def _primary_frame() -> pl.DataFrame:
    expo = variant_exposure(_PRIMARY)
    return expo.select(
        pl.col("industry_short").alias("industry"),
        "z_delegation",
        "z_delegation_lb",
        "z_delegation_ub",
        "z_usage",
        "z_augmentation",
        "z_aioe",
    )


def _zero_line() -> str:
    return ZERO_ASSIGNED_NOTE.format(zero_assigned_share(_PRIMARY)) + (
        " (the primary Design B exposure; this row rebuilds no index)."
    )


def run_market_row(row_id: str, *, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Run a Task 8 market row's parts on the primary exposure and write `R<nn>.csv` / `.md`."""
    row = MARKET_ROWS[row_id]
    frame = _primary_frame()
    records: list[dict] = []
    for part, kw in row.parts:
        records += market_variant(row_id, part, frame, label=row.label, **kw)
    notes = [*row.notes]
    if row.extra is not None:
        notes += row.extra(records, frame)
    notes += [_MARKET_ROW_NOTE, _zero_line()]
    return report.write_row(row_id, records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


_R35_NOTES = (
    "Studentised statistic (PAP §8.2 R35, P10): for each of the 378 pre-seal windows w, Σ_w is "
    "the covariance of the industries' daily FF5+UMD residuals (denominator T_w − 7), c_w = "
    "[(X_w′X_w)⁻¹]₁₁ is the intercept element of the common factor design, ω the OLS weight "
    "vector with b = ω′α ([1, z] for H5, [1, z, z_aioe] for H5b), SE_Σ,w = 252·√(c_w·ω′Σ_wω), "
    "and κ = sd_w(b_w)/median_w(SE_Σ,w), the same sd as s.",
    "[default] In the confirmatory window SE_Σ is computed the same way; stat = T_stud = "
    "(b̂ − b₀)/(κ·SE_Σ) with b₀ = b̄ (D21), p from t₂₁, and the t₂₁ criticals of §3.3. The "
    "scale column is κ·SE_Σ in pp and the interval is b̂ ± t₂₁,0.975·κ·SE_Σ, the §3.3 interval "
    "form with this scale, a presentation-only reading (PAP §11 C-75).",
    _MARKET_ROW_NOTE,
)


def _r35_records(frame: pl.DataFrame) -> list[dict]:
    rs = RETURN_SET
    end = confirm_h5.WINDOW[1]
    r = returns.load_return_set(rs, end)  # guarded before anything else
    f = returns.load_factors(end)
    names = [c for c in r.columns if c != "date"]
    if sorted(frame["industry"].to_list()) != sorted(names):
        raise ValueError(f"exposure industries do not match the {rs} return columns")
    by = {x["industry"]: x for x in frame.iter_rows(named=True)}
    a = market._window_alphas(rs, names, None)
    keep = ~np.isnan(a)
    kept = [n for n, k in zip(names, keep, strict=True) if k]
    dropped = [n for n, k in zip(names, keep, strict=True) if not k]
    ak = a[keep]
    z = np.array([by[n]["z_delegation"] for n in kept], dtype=float)
    c = np.array([by[n]["z_aioe"] for n in kept], dtype=float)
    A = market.history(rs, kept)
    t25, t5 = power.t_crit(0.025), power.t_crit(0.05)
    out = []
    for part, hyp, ctl in (("h5", "H5", None), ("h5b", "H5b", c)):
        ns = market.null_scales_for(z, ctl, A)
        w = power.ols_weights(z, ctl)
        b = float(w @ ak)
        k = studentised.kappa(z, ctl, rs, names=kept)
        se = studentised.se_sigma(r, f, *confirm_h5.WINDOW, w, kept)
        sc = k * se
        T = studentised.t_stud(b, ns.bbar, k, se)
        T0 = studentised.t_stud(b, 0.0, k, se)
        est = "slope of annualised FF5+UMD alpha on z_delegation" + (
            ", controlling for z_aioe" if ctl is not None else ""
        )
        control = "z_aioe" if ctl is not None else None
        rec = {
            "row_id": "R35",
            "part": part,
            "variant": (
                f"returns={rs}; z=z_delegation; control={control}; scale=kappa*SE_Sigma; "
                f"first={power.FIRST_START}; drop=none; statistic=T_stud; criticals=t21"
            ),
            "applies_to": hyp,
            "label": "robustness",
            "estimand": est,
            "unit": report.MARKET_UNIT,
            "estimate": b * 100,
            "scale": sc * 100,
            "ci_lo": (b - t5 * sc) * 100,
            "ci_hi": (b + t5 * sc) * 100,
            "stat": T,
            "p": market._p_t(T),
            "null": market.NULL,
            "crit_0025": t25,
            "crit_005": t5,
            "n": len(kept),
            "n_dropped": len(dropped),
            "dropped": ", ".join(dropped),
            "note": (
                f"κ = {report.fmt_stat(k)}; SE_Σ,2025–26 = {report.fmt_pp(se * 100)} pp; "
                f"b̄ = {report.fmt_pp(ns.bbar * 100)} pp; secondary b = 0: T = "
                f"{report.fmt_stat(T0)}, p = {report.fmt_p(market._p_t(T0))}"
            ),
        }
        report.check_record(rec)
        out.append(rec)
    return out


def run_R35(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R35: the studentised statistic T_stud on the primary Design B exposure."""
    records = _r35_records(_primary_frame())
    notes = [*_R35_NOTES, _zero_line()]
    return report.write_row("R35", records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


def _market_runner(row_id: str) -> Callable[..., tuple[Path, Path]]:
    def run(*, out_dir: Path | None = None) -> tuple[Path, Path]:
        return run_market_row(row_id, out_dir=out_dir)

    run.__name__ = f"run_{registry.output_stem(row_id)}"
    run.__doc__ = f"PAP §8.2 {row_id} on the primary Design B exposure."
    return run


# --- Task 9: new-data market rows R6 (FF30/FF48) and R32 (strict real-time Design B) -----

_FF_VINTAGE = (
    "FF30/FF48 files retrieved after the freeze; their history may reflect French's later "
    "revisions. French's newer download vintage applies to these files only: FF49 and the "
    "factors stay the frozen files (PAP §8.2 R6, §9.1)."
)
_NEWDATA_MARKET_NOTE = (
    "Market parts: H5 and H5b on each part's return set with s, b̄ and q recomputed for the "
    "part's exposure vector on the same 378 pre-seal windows with the same code, the critical "
    "max(t₂₁, q) and the D21 null b₀ = b̄ (PAP §3.3, §8.1); industries with a missing return "
    "in the confirmatory window are dropped and z is not re-standardised after a drop. The "
    "secondary b = 0 statistic is in each record's note."
)


@dataclass(frozen=True)
class NewDataRow:
    row_id: str
    parts: tuple[tuple[str, ExposureSpec, str], ...]  # (part, exposure spec, return set)
    notes: tuple[str, ...]
    label: str = "robustness"


NEWDATA_ROWS: dict[str, NewDataRow] = {
    r.row_id: r
    for r in (
        NewDataRow(
            "R6",
            (
                ("ff30", ExposureSpec(industries=30), "ff30_vw"),
                ("ff48", ExposureSpec(industries=48), "ff48_vw"),
            ),
            (
                "FF30 and FF48 industry granularity (PAP §8.2 R6): the exposure is rebuilt on "
                "the 30 / 48 industries of Siccodes30 / Siccodes48 with the same split "
                "crosswalk, z re-standardised across those industries; alphas from the 30- / "
                "48-industry daily value-weighted files; s, b̄ and q from the same 378 windows "
                "on those files.",
                _FF_VINTAGE,
                _BENCH_REAGG,
            ),
        ),
        NewDataRow(
            "R32",
            (("market", ExposureSpec(oews_year=2023, onet="29.2"), RETURN_SET),),
            (
                "Strict real-time Design B (PAP §8.2 R32, P15): release r2 with OEWS May 2023 "
                "weights (oesm23in4, oesm23nat) and O*NET task statements ≤ 29.2, i.e. inputs "
                "public at 2025-03-27; s, b̄ and q recomputed.",
                "The O*NET 29.2 Task Statements file is byte-identical to the 29.3 file of the "
                "primary, so R32's task index equals the primary's and R32 differs from the "
                "primary only through the OEWS May 2023 weights (PAP §11 C-74).",
                _BENCH_REAGG,
            ),
        ),
    )
}


def run_newdata_row(row_id: str, *, out_dir: Path | None = None) -> tuple[Path, Path]:
    """Run a Task 9 row: each part rebuilds its exposure and runs H5/H5b on its return set."""
    row = NEWDATA_ROWS[row_id]
    records: list[dict] = []
    variant_lines: list[str] = []
    zero_lines: list[str] = []
    for part, spec, rs in row.parts:
        desc = describe_spec(spec)
        expo = variant_exposure(spec)
        frame = expo.select(pl.col("industry_short").alias("industry"), "z_delegation", "z_aioe")
        recs = market_variant(row_id, part, frame, rs=rs, label=row.label)
        records += [r | {"variant": f"{desc}; {r['variant']}"} for r in recs]
        variant_lines.append(
            f"Variant {part}: {desc} on {rs} ({expo.height} industries); every other "
            "construction choice is the primary Design B one."
        )
        zero_lines.append(f"{part}: " + ZERO_ASSIGNED_NOTE.format(zero_assigned_share(spec)))
    notes = [*variant_lines, *row.notes, *zero_lines, _NEWDATA_MARKET_NOTE]
    return report.write_row(row_id, records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


def _newdata_runner(row_id: str) -> Callable[..., tuple[Path, Path]]:
    def run(*, out_dir: Path | None = None) -> tuple[Path, Path]:
        return run_newdata_row(row_id, out_dir=out_dir)

    run.__name__ = f"run_{registry.output_stem(row_id)}"
    run.__doc__ = f"PAP §8.2 {row_id} (new data)."
    return run


run_R06 = _newdata_runner("R6")
run_R32 = _newdata_runner("R32")

run_R05 = _market_runner("R5")
run_R07 = _market_runner("R7")
# Task 8's market parts of R10; Task 11's `run_R10` carries their committed records
run_R10_market = _market_runner("R10")
run_R18 = _market_runner("R18")
run_R19 = _market_runner("R19")
run_R21 = _market_runner("R21")
run_R34 = _market_runner("R34")

# --- Task 10: Design A and event rows R4, R8, R9, R16 ---------------------------------------

WORK_DIR: Path = upstream.WORK_DIR  # untracked: Plan 3's runner docs for the variant runs
DESIGN_A_LABEL = "robustness; exploratory"
DESIGN_A_PARTS = ("terciles", "fm", "events")
PLACEBO_YEARS = (2017, 2018, 2019, 2021)  # PAP §8.2 R9: 2020 skipped
R9_HORIZONS = (5, 20)
R4_SPEC = ExposureSpec(design="A_pooled", source="1p_api")
R16_SPEC = ExposureSpec(design="A_pooled", r6_basis="tasks")
LOOK_AHEAD_A = "A_pooled"

_TERC_UNITS = {
    "alpha_CAPM": "annualised pp",
    "alpha_FF3": "annualised pp",
    "alpha_FF5+UMD": "annualised pp",
    "mean": "annualised pp",
    "sharpe": "annualised Sharpe ratio",
    "psr": "probability",
    "dsr": "probability",
}
_FM_UNITS = {
    "z": "pp per month per 1 SD",
    "log_size": "pp per month per unit of log size",
    "log_beme": "pp per month per unit of log BE/ME",
    "mom": "pp per month per unit of the 12-2 return (decimal)",
}
_EVENT_UNIT = "pp of CAR per 1 SD"
_APPLIES = {
    "terciles": "terciles",
    "fm": "Fama-MacBeth",
    "events": "event studies",
    "placebo": "event studies",
}

_DESIGN_A_NOTE = (
    "Design A parts run Plan 3's own runners on the exposure frame passed: `run_terciles` "
    "(fixed-membership H-L terciles, cap and EW legs; C-34, C-35, C-37, C-45), `run_fm` "
    "(Fama–MacBeth on [1, z, log size, log BE/ME, 12-2 momentum]; C-38, C-46) and `run_events` "
    "(the 14 D19 events, CAR slopes at horizons 5 and 20, HC3 normal reference; C-33, C-44). "
    "Records are read from the frames the runners return; their docs are written under the "
    "untracked `data/derived/robustness/<row>/<part>` and no figure is written."
)
_DESIGN_A_COLUMNS = (
    "Columns: estimate, interval and p are as Plan 3 returns them; the scale column holds the "
    "SE (Newey-West for terciles and Fama–MacBeth, HC3 for event slopes); n is T (months) for "
    "terciles and Fama–MacBeth and the number of industries for event slopes. Null 0, nominal "
    "and single-test; no error control across records or rows (PAP §8.1). Sharpe, PSR and DSR "
    "carry no p; PSR and DSR carry no interval."
)
_R9_COLUMNS = (
    "Columns: placebo records hold the CAR slope as estimate, its HC3 SE in the scale column, "
    "and the interval and p as Plan 3's `run_events` returns them, with n the number of "
    "industries and null 0, nominal and single-test. Summary records hold the mean actual "
    "slope as estimate and its percentile in the stat column, with n the number of placebo "
    "slopes and no null, interval or p. No error control across records or rows (PAP §8.1)."
)
_R4_BOOT = (
    "Bootstrap draws: `run_terciles` consumes one `default_rng(SEED)` in `VARIANTS` order "
    "(PAP §11 C-37); with only A_pooled passed its variants draw first, so the mean and Sharpe "
    "bootstrap CIs use different draws from the primary run's A_pooled rows. A CI difference "
    "against the primary is partly draw noise, not only the exposure change."
)
_R8_BOOT = (
    "Bootstrap draws: with Design B absent and 33 months, the one `default_rng(SEED)` "
    "(consumed in `VARIANTS` order, PAP §11 C-37) gives the A_r2 and A_pooled variants "
    "different draws from the primary run, so their bootstrap CIs differ partly by draw noise."
)


def placebo_events() -> tuple[Event, ...]:
    """PAP §8.2 R9 (C-60): each D19 event's month and day in 2017, 2018, 2019 and 2021, named
    `"<event> placebo <year>"` (never exactly `ESZ_EVENT`, so no Eisfeldt step runs)."""
    return tuple(
        Event(f"{e.name} placebo {y}", date(y, e.announced.month, e.announced.day))
        for e in upstream.EVENTS
        for y in PLACEBO_YEARS
    )


def _month_ends(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(date(y, m, calendar.monthrange(y, m)[1]))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def months_without_2023() -> dict[str, list[date]]:
    """PAP §8.2 R8: every month end of the Design A window whose year is not 2023."""
    return {"A": [m for m in _month_ends(*upstream.WINDOWS["A"]) if m.year != 2023]}


def placebo_percentile(actual: float, placebo: Sequence[float]) -> float:
    """Empirical percentile of `actual` among `placebo`: 100 x the share of placebo values
    <= actual."""
    v = np.asarray(placebo, dtype=float)
    return float(100.0 * np.mean(v <= actual))


def _design_label(d: str | None) -> str:
    if d is None:
        return "none"
    return f"{d} (look-ahead)" if d == LOOK_AHEAD_A else d


def _a_record(
    row_id: str,
    part: str,
    variant: str,
    estimand: str,
    unit: str,
    r: dict,
    *,
    est: str,
    scale: str | None,
    n: int | None,
    note: str,
) -> dict:
    rec = {
        "row_id": row_id,
        "part": part,
        "variant": variant,
        "applies_to": _APPLIES.get(part, part),
        "label": DESIGN_A_LABEL,
        "estimand": estimand,
        "unit": unit,
        "estimate": r[est],
        "scale": None if scale is None else r[scale],
        "ci_lo": r["ci_lo"],
        "ci_hi": r["ci_hi"],
        "stat": None,
        "p": r["p"],
        "null": "0",
        "crit_0025": None,
        "crit_005": None,
        "n": n,
        "n_dropped": None,
        "dropped": None,
        "note": note,
    }
    report.check_record(rec)
    return rec


def _tercile_records(row_id: str, df: pl.DataFrame, variant: str) -> list[dict]:
    out = []
    for r in df.iter_rows(named=True):
        est = f"{r['statistic']} {r['design']} {r['weighting']}"
        note = f"{est}; {_design_label(r['design'])}; nominal"
        out.append(
            _a_record(
                row_id,
                "terciles",
                variant,
                est,
                _TERC_UNITS[r["statistic"]],
                r,
                est="estimate",
                scale="se",
                n=r["T"],
                note=note,
            )
        )
    return out


def _fm_records(row_id: str, df: pl.DataFrame, variant: str) -> list[dict]:
    out = []
    for r in df.iter_rows(named=True):
        est = f"FM {r['regressor']} {r['design']}"
        note = (
            f"{est}; {_design_label(r['design'])}; window {r['window']}; mean n "
            f"{r['n_mean']:.1f}; {r['skipped']} months skipped; nominal"
        )
        out.append(
            _a_record(
                row_id,
                "fm",
                variant,
                est,
                _FM_UNITS[r["regressor"]],
                r,
                est="mean",
                scale="se",
                n=r["T"],
                note=note,
            )
        )
    return out


def _event_estimand(r: dict) -> str:
    est = f"CAR slope {r['event']} h{r['horizon']} {r['design'] or 'none'}"
    if r["regressors"] != "z_delegation":
        est += f" [{r['regressor']} in {r['regressors']}]"
    return est


def _event_records(row_id: str, part: str, df: pl.DataFrame, variant: str) -> list[dict]:
    out = []
    for r in df.iter_rows(named=True):
        est = _event_estimand(r)
        note = f"{est}; day 0 {r['day0']}; {_design_label(r['design'])}; nominal"
        out.append(
            _a_record(
                row_id, part, variant, est, _EVENT_UNIT, r, est="b", scale="se", n=r["n"], note=note
            )
        )
    return out


def _variant_desc(expo: pl.DataFrame, months: dict | None) -> str:
    designs = [d for d in upstream.RQ3_DESIGNS if d in set(expo["design"].to_list())]
    ms = (
        "full windows"
        if not months
        else "; ".join(f"window {k}: {len(v)} month ends" for k, v in sorted(months.items()))
    )
    return f"designs {', '.join(designs)}; {ms}"


def design_a_records(
    row_id: str,
    expo: pl.DataFrame,
    *,
    months: dict | None = None,
    parts: tuple[str, ...] = DESIGN_A_PARTS,
) -> list[dict]:
    """Run Plan 3's terciles, Fama–MacBeth and events on `expo` (Plan 3's exposure frame) with
    `out_dir = WORK_DIR / row_id / part` and no figure, and map the returned rows to
    `ROBUSTNESS_COLUMNS`. `months` goes to the terciles and Fama–MacBeth only."""
    unknown = [p for p in parts if p not in DESIGN_A_PARTS]
    if unknown:
        raise ValueError(f"unknown Design A parts {unknown}")
    variant = _variant_desc(expo, months)
    out: list[dict] = []
    for part in parts:
        od = WORK_DIR / row_id / part
        if part == "terciles":
            df = upstream.run_terciles(od, months=months, expo=expo)
            out += _tercile_records(row_id, df, variant)
        elif part == "fm":
            df = upstream.run_fm(od, months=months, expo=expo)
            out += _fm_records(row_id, df, variant)
        else:
            if months is not None:
                raise ValueError("run_events takes no months")
            df = upstream.run_events(od, expo=expo)
            out += _event_records(row_id, "events", df, variant)
    return out


def _dsr_note(records: list[dict]) -> str:
    n = len(
        {
            (r["estimand"].split()[1], r["estimand"].split()[2])
            for r in records
            if r["part"] == "terciles"
        }
    )
    return (
        f"DSR here is against the {n} tercile variants run in this row (the primary used 6, "
        "C-37); not comparable with the primary's DSR (PAP §11 C-76)."
    )


def _with_note(records: list[dict], part: str, extra: str) -> list[dict]:
    return [r | {"note": f"{r['note']}; {extra}"} if r["part"] == part else r for r in records]


def _primary_a(*designs: str) -> pl.DataFrame:
    """Plan 3's primary exposure frame (hash-checked `data.exposures()`), these designs only."""
    return upstream.exposures().filter(pl.col("design").is_in(list(designs)))


def _primary_zero_lines(designs: Sequence[str]) -> list[str]:
    return upstream.zero_assigned_lines(list(designs), upstream.zero_assigned())


def _index_record(row_id: str, variant: pl.DataFrame, desc: str) -> dict:
    from scipy.stats import spearmanr

    prim = _primary_a("A_pooled").select("ff49", pl.col("z_delegation").alias("z_primary"))
    j = (
        variant.select(pl.col("industry").alias("ff49"), "z_delegation")
        .join(prim, on="ff49", how="inner")
        .drop_nulls()
    )
    rho = float(spearmanr(j["z_delegation"].to_numpy(), j["z_primary"].to_numpy()).statistic)
    rec = {
        "row_id": row_id,
        "part": "index",
        "variant": f"{desc}; vs primary A_pooled",
        "applies_to": "A_pooled",
        "label": DESIGN_A_LABEL,
        "estimand": "spearman variant A_pooled z_delegation vs primary A_pooled z_delegation",
        "unit": report.RHO_UNIT,
        "estimate": rho,
        "scale": None,
        "ci_lo": None,
        "ci_hi": None,
        "stat": None,
        "p": None,
        "null": None,
        "crit_0025": None,
        "crit_005": None,
        "n": j.height,
        "n_dropped": None,
        "dropped": None,
        "note": "variant vs primary A_pooled z_delegation (Spearman, FF49 industries with both "
        "values); descriptive, no interval",
    }
    report.check_record(rec)
    return rec


def _r6_inputs():
    """Plan 2's anatomy inputs: the study panel, O*NET index, May 2024 wages and national
    employment, and the AEI SOC structure (as `results.rq1.report_anatomy` loads them)."""
    from aideleg.bls.oews import load_national

    inp = upstream.rq1_inputs()
    return inp.panel, inp.index, inp.wages, load_national(2024), inp.soc_structure


def _r6_descriptive_records(row_id: str, desc: str) -> list[dict]:
    panel, index, wages, national, soc = _r6_inputs()
    tab = {
        b: upstream.by_wage_decile(
            panel, index, wages, national, soc, release="r6", source="claude_ai", basis=b
        )
        for b in ("tasks", "published")
    }
    pub = {r["decile"]: r for r in tab["published"].iter_rows(named=True)}
    cols = [
        c for c in tab["tasks"].columns if c not in ("decile", "emp_share", "usage_share", "n_occ")
    ]
    out = []
    for r in tab["tasks"].iter_rows(named=True):
        d = r["decile"]
        lab = "no wage" if d is None else str(d)
        for c in cols:
            pv = pub[d][c] if d in pub else None
            rec = {
                "row_id": row_id,
                "part": "r6_descriptives",
                "variant": f"{desc}; r6 claude_ai by_wage_decile basis=tasks vs published",
                "applies_to": "r6 descriptives",
                "label": DESIGN_A_LABEL,
                "estimand": f"r6 wage decile {lab} {c}",
                "unit": "percent (usage-weighted mean pattern share)",
                "estimate": r[c],
                "scale": None,
                "ci_lo": None,
                "ci_hi": None,
                "stat": None,
                "p": None,
                "null": None,
                "crit_0025": None,
                "crit_005": None,
                "n": r["n_occ"],
                "n_dropped": None,
                "dropped": None,
                "note": f"published: {report.fmt_pp(pv)}; decile {lab} {c}; task basis "
                f"(n = OEWS occupations in the decile); descriptive",
            }
            report.check_record(rec)
            out.append(rec)
    return out


def _pooled_row(
    row_id: str,
    spec: ExposureSpec,
    extra_notes: Sequence[str],
    *,
    descriptives: bool,
    out_dir: Path | None,
) -> tuple[Path, Path]:
    desc = describe_spec(spec)
    variant = variant_exposure(spec)
    row = ExposureRow(row_id, spec, ("rq2",), DESIGN_A_LABEL, ())
    records = _rq2_records(row, variant, desc)
    records.append(_index_record(row_id, variant, desc))
    recs = design_a_records(row_id, upstream.to_rq3_expo(variant, "A_pooled"))
    records += _with_note(
        [r | {"variant": f"{desc}; {r['variant']}"} for r in recs],
        "terciles",
        _R4_BOOT if row_id == "R4" else _R16_BOOT,
    )
    if descriptives:
        records += _r6_descriptive_records(row_id, desc)
    notes = [
        f"Variant: {desc}; every other construction choice is the primary A_pooled one. "
        "A_pooled is labelled look-ahead (PAP §8.3 D19).",
        *extra_notes,
        ZERO_ASSIGNED_NOTE.format(zero_assigned_share(spec)),
        _RQ2_NOTE,
        "Index part: the Spearman correlation of the variant A_pooled `z_delegation` with the "
        "primary A_pooled `z_delegation` (Plan 3's `data.exposures()`), across the FF49 "
        "industries with both values; descriptive.",
        _DESIGN_A_NOTE,
        _DESIGN_A_COLUMNS,
        _dsr_note(records),
    ]
    return report.write_row(row_id, records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


_R16_BOOT = _R4_BOOT  # the same mechanism, the same wording (PAP §11 C-76)


def run_R04(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R4: A_pooled from the `1p_api` source, pooled over r3–r6."""
    return _pooled_row(
        "R4",
        R4_SPEC,
        (
            "`1p_api` in place of `claude_ai` for A_pooled, pooled over r3–r6 with equal release "
            "weights: the API source starts at r3 (PAP §8.2 R4; §11 C-65). Design B has no API "
            "source. For RQ1 this variant is merged into R22 and R24 (PAP §8.2 R4).",
            _BENCH_PRIMARY,
            _R4_BOOT,
        ),
        descriptives=False,
        out_dir=out_dir,
    )


def run_R16(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R16: the r6 task-allocated occupation basis, for A_pooled and r6 descriptives."""
    return _pooled_row(
        "R16",
        R16_SPEC,
        (
            'r6 occupation tables on the task-allocated basis (`basis="tasks"`) in place of '
            "AEI's published SOC rows, in the A_pooled pool r2–r6 (PAP D9 alternative, §8.2 "
            "R16).",
            _BENCH_PRIMARY,
            _R16_BOOT,
            'r6 descriptives: Plan 2\'s `by_wage_decile` (r6, `claude_ai`) on `basis="tasks"` '
            'beside `basis="published"` with the same inputs; one record per (decile, pattern) '
            "cell, the estimate the task-basis value and the published value in the note.",
        ),
        descriptives=True,
        out_dir=out_dir,
    )


def run_R08(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R8: Design A terciles and Fama–MacBeth with calendar 2023 excluded."""
    designs = ("A_r2", "A_pooled")
    months = months_without_2023()
    recs = design_a_records("R8", _primary_a(*designs), months=months, parts=("terciles", "fm"))
    recs = [r | {"variant": f"primary Design A exposures; {r['variant']}"} for r in recs]
    records = _with_note(recs, "terciles", _R8_BOOT)
    ms = months["A"]
    notes = [
        f"Calendar 2023 excluded (PAP §8.2 R8): the Design A terciles' months and the "
        f"Fama–MacBeth monthly cross-sections use the {len(ms)} month ends of 2022-12 to "
        f"2026-08 outside 2023 ({ms[0]:%Y-%m}, then {ms[1]:%Y-%m} to {ms[-1]:%Y-%m}); the "
        "Newey-West SEs run on those months only. No null scale is involved.",
        "Not applicable to Design B by design (its window starts 2025-04; PAP §8.2 R8). Event "
        "studies are not part of R8.",
        "Exposure: Plan 3's primary A_r2 and A_pooled `z_delegation` (A_pooled labelled "
        "look-ahead, PAP §8.3 D19); this row rebuilds no index.",
        *_primary_zero_lines(designs),
        _R8_BOOT,
        _DESIGN_A_NOTE,
        _DESIGN_A_COLUMNS,
        _dsr_note(records),
    ]
    return report.write_row("R8", records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


def _r9_slopes(df: pl.DataFrame, h: int) -> pl.DataFrame:
    return df.filter(
        (pl.col("horizon") == h)
        & (pl.col("design") == "A_r2")
        & (pl.col("regressors") == "z_delegation")
    )


def run_R09(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R9 (C-60): placebo event dates on the primary A_r2 `z_delegation`."""
    expo = _primary_a("A_r2")
    events = placebo_events()
    plc = upstream.run_events(WORK_DIR / "R9", events=events, expo=expo)
    act = upstream.run_events(WORK_DIR / "R9_actual", expo=expo)
    variant = "primary A_r2 z_delegation; placebo day-0 dates"
    records: list[dict] = []
    for h in R9_HORIZONS:
        records += _event_records("R9", "placebo", _r9_slopes(plc, h), variant)
    for h in R9_HORIZONS:
        p = _r9_slopes(plc, h)["b"].to_list()
        a = _r9_slopes(act, h)["b"].to_list()
        if len(p) != len(events) or len(a) != len(upstream.EVENTS):
            raise ValueError(f"R9 h{h}: {len(p)} placebo and {len(a)} actual slopes")
        mean_a = float(np.mean(a))
        rec = {
            "row_id": "R9",
            "part": "summary",
            "variant": f"primary A_r2 z_delegation; D19 events vs {len(p)} placebo dates",
            "applies_to": "event studies",
            "label": DESIGN_A_LABEL,
            "estimand": f"mean CAR slope h{h} A_r2 over the {len(a)} D19 events",
            "unit": _EVENT_UNIT,
            "estimate": mean_a,
            "scale": None,
            "ci_lo": None,
            "ci_hi": None,
            "stat": placebo_percentile(mean_a, p),
            "p": None,
            "null": None,
            "crit_0025": None,
            "crit_005": None,
            "n": len(p),
            "n_dropped": None,
            "dropped": None,
            "note": (
                f"[default] mean of the {len(a)} actual D19 slopes at h{h}; stat = its empirical "
                f"percentile among the {len(p)} placebo slopes (100 × share of placebo slopes ≤ "
                f"the mean, out of {len(p)}; PAP §11 C-76); n = placebo slopes; descriptive"
            ),
        }
        report.check_record(rec)
        records.append(rec)
    notes = [
        "[default] Placebo day-0 dates (PAP §8.2 R9; §11 C-60): each of the 14 D19 events' "
        'month and day in 2017, 2018, 2019 and 2021 (56 dates, named "<event> placebo '
        '<year>"); 2020 is skipped, as the PAP states. Day 0 is the next trading day when the '
        "date is not one (Plan 3's `day_zero`).",
        "The placebo dates are not D19 events. Plan 3's `event_study.md` for this run (in the "
        "untracked work directory) prints the D19 rule text whatever events it is given; the "
        "records here are read from the frame `run_events` returns, not from that doc. No "
        "placebo is named `ChatGPT`, so no Eisfeldt et al. step runs on them.",
        "[default] Placebo records: the CAR slope on the primary A_r2 `z_delegation` at "
        "horizons 5 and 20, one per placebo date and horizon, as Plan 3's `run_events` returns "
        "it (OLS with intercept, HC3, normal reference; C-44). Summary records: per horizon, "
        "the mean A_r2 slope over the 14 actual D19 events (a second `run_events` on the same "
        "exposure) and its empirical percentile among the 56 placebo slopes, in the stat "
        "column; descriptive, no p (PAP §11 C-60).",
        "[default] Percentile convention: 100 × the share of the 56 placebo slopes ≤ the actual "
        "mean slope, per horizon (PAP §11 C-76).",
        "Exposure: Plan 3's primary A_r2 `z_delegation`; this row rebuilds no index.",
        *_primary_zero_lines(("A_r2",)),
        _R9_COLUMNS,
    ]
    return report.write_row("R9", records, notes, out_dir=OUT_DIR if out_dir is None else out_dir)


# --- Task 11: H1/H3 rows R10 (RQ1 parts), R23 (H1), R24, R26, R27, R31, R38 ----------------

H1_COVARIATES = ("human_education_years_mean", "log_wage")
_RQ1_NOTE_TEMPLATE = (
    "RQ1 parts: Plan 2's `estimate_h1` / `estimate_h3` on Plan 2's `build_task_rows` (through "
    "the adapter), with the inference of the hypothesis varied (PAP §8.1): WLS with IWA fixed "
    "effects unless the row says otherwise, two-way cluster-robust SEs by occupation (soc6) and "
    "task, t with min(G_occ, G_task) − 1 df and the PAP §4 non-PSD rule (each use is in the "
    "record's note). `scale` is the SE, `stat` the t statistic, intervals 95%, p two-sided; "
    "p_H1 = max(p_educ, p_wage) (D17). Coefficients are in {units}. Each table row's note "
    "cell starts with its coefficient (PAP §11 C-78). `n` is the number of (task, occupation, "
    "family) rows; `dropped` lists the non-zero drop shares in % of total task usage, structural "
    "then variable-level (PAP §4.1, §11 C-2, C-30); `n_dropped` is not reported for RQ1 rows, "
    "because Plan 2 records drops as usage shares, not row counts (PAP §11 C-2, C-78)."
)
_PP_UNITS = "pp of the outcome share per unit of the regressor"


def _rq1_note(units: str = _PP_UNITS) -> str:
    return _RQ1_NOTE_TEMPLATE.format(units=units)


# names of the coefficients in the RQ1 .md tables (PAP §11 C-78); the CSV keeps `estimand`
RQ1_LABELS = {
    "human_education_years_mean": "education",
    "log_wage": "log wage",
    "p_H1": "p_H1",
    "error_cost": "error cost",
    "coe": "Consequence of Error",
}
_R23_ALWAYS = (
    "R23 is reported beside H1 (PAP §4.1): the H1 decision uses `automation_pct` only and is "
    "unchanged. The PAP §4.1 disagreement sentence is printed below only if each R23 "
    "coefficient (education, log wage) has the sign opposite to the committed primary H1 "
    "coefficient (P-RQ1 record) and p < 0.05, a mechanical check (PAP §11 C-77)."
)
_R23_SIGN_LINE = (
    "Sign check against the committed primary H1 (P-RQ1): education R23 {b_e} vs primary "
    "{b0_e}, {s_e} sign, p {p_e}; log wage R23 {b_w} vs primary {b0_w}, {s_w} sign, p {p_w} "
    "(PAP §11 C-77)"
)


def r23_sign_line(res: upstream.HypothesisResult, primary: dict[str, float]) -> str:
    """The R23 sign comparison, printed whatever `rq1.r23_disagrees` returns (PAP §11 C-77)."""
    vals = {}
    for key, name in (("e", "human_education_years_mean"), ("w", "log_wage")):
        c, b0 = res.coefs[name], primary[name]
        vals |= {
            f"b_{key}": report.fmt_pp(c.estimate),
            f"b0_{key}": report.fmt_pp(b0),
            f"s_{key}": "opposite" if c.estimate * b0 < 0 else "same",
            f"p_{key}": report.fmt_p(c.p),
        }
    return _R23_SIGN_LINE.format(**vals)


def _rq1_part(
    row_id: str,
    part: str,
    tr: upstream.TaskRows,
    res: upstream.HypothesisResult,
    *,
    extra: Sequence[str] = (),
    se_key: str | None = None,
    label: str = "robustness",
) -> list[dict]:
    variant = "; ".join(
        [
            f"release={tr.release}",
            f"source={tr.source}",
            f"family={tr.family_level}",
            f"outcome={res.outcome}",
            *extra,
        ]
    )
    recs = rq1.rq1_records(row_id, part, res, label=label, se_key=se_key)
    return [r | {"variant": variant} for r in recs]


def _both(row_id: str, part: str, tr: upstream.TaskRows) -> list[dict]:
    """H1 then H3, primary specification, on `tr`."""
    return [
        *_rq1_part(row_id, part, tr, upstream.estimate_h1(tr)),
        *_rq1_part(row_id, part, tr, upstream.estimate_h3(tr)),
    ]


def _md_label(r: dict) -> dict:
    """An RQ1 record with its coefficient leading the note cell (PAP §11 C-78)."""
    if r["applies_to"] not in ("H1", "H3"):
        return r
    name = RQ1_LABELS.get(r["estimand"], r["estimand"])
    return r | {"note": f"{name}: {r['note']}" if r["note"] else name}


def _write(row_id: str, records: list[dict], notes: list[str], out_dir: Path | None):
    """`write_row` with the RQ1 coefficients labelled in the `.md` table only; the CSV is then
    rewritten from the unlabelled records, so it keeps `estimand` and the plain notes (C-78)."""
    out = OUT_DIR if out_dir is None else out_dir
    labelled = [_md_label(r) for r in records]
    csv_path, md_path = report.write_row(row_id, labelled, notes, out_dir=out)
    df = pl.DataFrame(
        [{k: r[k] for k in report.ROBUSTNESS_COLUMNS} for r in records], infer_schema_length=None
    )
    report.write_csv(df.select(report.ROBUSTNESS_COLUMNS), csv_path)
    return csv_path, md_path


_FLOAT_COLS = frozenset(
    ("estimate", "scale", "ci_lo", "ci_hi", "stat", "p", "crit_0025", "crit_005")
)
_INT_COLS = frozenset(("n", "n_dropped"))
R10_MARKET_PARTS = ("market_lb", "market_ub")


def _csv_value(col: str, v: str):
    if col in _FLOAT_COLS:
        return float(v) if v != "" else None
    if col in _INT_COLS:
        return int(v) if v != "" else None
    return v


def r10_market_carry(out_dir: Path) -> tuple[list[dict], list[str]]:
    """Task 8's committed R10 market records and notes, read back from `R10.csv` / `R10.md`
    (no market read): the `market_*` records verbatim, and the notes Task 8 wrote (its row
    notes, the market-row note and the zero-assigned line)."""
    csv_path, md_path = Path(out_dir) / "R10.csv", Path(out_dir) / "R10.md"
    with csv_path.open(newline="", encoding="utf-8") as f:
        rdr = csv.DictReader(f)
        if rdr.fieldnames != report.ROBUSTNESS_COLUMNS:
            raise ValueError(f"{csv_path}: columns differ from ROBUSTNESS_COLUMNS")
        records = [
            {k: _csv_value(k, v) for k, v in row.items()}
            for row in rdr
            if row["part"] in R10_MARKET_PARTS
        ]
    if sorted({r["part"] for r in records}) != sorted(R10_MARKET_PARTS):
        raise ValueError(f"{csv_path}: the committed market parts {R10_MARKET_PARTS} are missing")
    lines = md_path.read_text(encoding="utf-8").splitlines()
    i, j = lines.index("## Notes"), lines.index("## Results")
    known = {*MARKET_ROWS["R10"].notes, _MARKET_ROW_NOTE}
    zero = ZERO_ASSIGNED_NOTE.split("{")[0]
    notes = [
        ln[2:]
        for ln in lines[i + 1 : j]
        if ln.startswith("- ") and (ln[2:] in known or ln[2:].startswith(zero))
    ]
    if len(notes) != len(known) + 1:
        raise ValueError(f"{md_path}: Task 8's market notes not found ({len(notes)} of 3)")
    return records, notes


_R6_SUPP = " + ".join(f"`{c}`" for c in SUPPRESSION["r6"])


def run_R10(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R10: the RQ1 parts (H1 and H3 on the D1 suppression bounds) beside the
    committed market parts, which are carried, not re-run."""
    guards.require_rq1_run_committed()
    out = OUT_DIR if out_dir is None else Path(out_dir)
    market_records, market_notes = r10_market_carry(out)
    tr = upstream.task_rows()
    records: list[dict] = []
    for b in ("lb", "ub"):
        res = upstream.estimate_h1(tr, outcome=f"automation_share_all_{b}")
        records += _rq1_part("R10", f"h1_{b}", tr, res)
    bounds = rq1.validation_bounds(upstream.rq1_inputs().panel, release="r6", source="claude_ai")
    tv = rq1.with_validation_bounds(tr, bounds)
    for b in ("lb", "ub"):
        res = upstream.estimate_h3(tv, outcome=f"validation_share_all_{b}")
        records += _rq1_part("R10", f"h3_{b}", tv, res)
    notes = [
        "RQ1 parts of R10 (PAP §8.2 R10, D1): H1 with `automation_share_all_lb` / `_ub` in "
        "place of `automation_pct` (parts h1_lb, h1_ub); Plan 2's builder computes the bounds "
        f"per period with r6's suppression component ({_R6_SUPP}) and then D13-averages them "
        "(PAP §11 C-4).",
        "[default] H3 with `validation_share_all_lb` = v·(100 − s)/100 and `_ub` = lb + s in "
        "place of `validation_pct` (parts h3_lb, h3_ub), v = `validation_pct` and s = r6's "
        f"suppression share ({_R6_SUPP}), per period and then D13-averaged, as for the "
        "automation bounds (PAP §11 C-57).",
        _rq1_note(),
    ]
    return _write("R10", market_records + records, market_notes + notes, out)


def run_R23(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R23, H1 part: `ai_autonomy_mean` as H1's delegation measure."""
    guards.require_rq1_run_committed()
    tr = upstream.task_rows()
    res = upstream.estimate_h1(tr, outcome="ai_autonomy_mean")
    records = _rq1_part("R23", "h1", tr, res)
    primary = {
        n: float(c["estimate"])
        for n, c in upstream.committed_rq1()["results"]["H1"]["coefs"].items()
    }
    notes = [
        "`ai_autonomy_mean` (D13-averaged, r6 `claude_ai`) in place of `automation_pct` as H1's "
        "outcome (PAP §8.2 R23, spec §5.4.1); same predictors, sample rule, fixed effects and "
        "inference. R23's H2 part is a separate Plan 4 task.",
        _R23_ALWAYS,
        r23_sign_line(res, primary),
    ]
    if rq1.r23_disagrees(res, primary):
        notes.append(
            "R23's education and log-wage coefficients both have the sign opposite to H1's "
            f"and are significant at nominal 0.05, so {rq1.R23_DISAGREE} (PAP §4.1); the H1 "
            "decision is unchanged."
        )
    notes.append(
        _rq1_note(
            "ai_autonomy_mean scale points per unit of the regressor (per year of education, "
            "per log point of wage)"
        )
    )
    return _write("R23", records, notes, out_dir)


R24_PARTS: tuple[tuple[str, dict], ...] = (
    ("r4", {"release": "r4"}),
    ("r5", {"release": "r5"}),
    ("r6_1p_api", {"source": "1p_api"}),
)
R26_PARTS: tuple[tuple[str, dict], ...] = (
    ("gwa", {"family_level": "gwa"}),
    ("dwa", {"family_level": "dwa"}),
)


def run_R24(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R24: H1 and H3 on r4 and r5 `claude_ai` and on r6 `1p_api` (D13)."""
    guards.require_rq1_run_committed()
    records: list[dict] = []
    for part, kw in R24_PARTS:
        records += _both("R24", part, upstream.task_rows(**kw))
    notes = [
        "D13 alternatives (PAP §8.2 R24): release r4 `claude_ai` (part r4), r5 `claude_ai` "
        "(r5) and r6 `1p_api` (r6_1p_api), each through Plan 2's builder for that release and "
        "source (D13 averaging over the release's periods; the R7 suppression components of "
        "that release), H1 and H3 with the primary specification otherwise.",
        _rq1_note(),
    ]
    return _write("R24", records, notes, out_dir)


def run_R26(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R26: H1 and H3 with GWA and with DWA task-family fixed effects (D14)."""
    guards.require_rq1_run_committed()
    records: list[dict] = []
    for part, kw in R26_PARTS:
        records += _both("R26", part, upstream.task_rows(**kw))
    notes = [
        "GWA (part gwa) and DWA (part dwa) task-family fixed effects in place of IWA (PAP §8.2 "
        "R26, D14), from Plan 2's `task_families(level)`; a task linked to several families is "
        "split equally across them and the family set is the union over the task's candidate "
        "Task IDs, as for IWA (D14, PAP §11 C-9).",
        _rq1_note(),
    ]
    return _write("R26", records, notes, out_dir)


def run_R27(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R27: H3 with the continuous O*NET Consequence of Error (D15 alternative)."""
    guards.require_rq1_run_committed()
    tr = upstream.task_rows()
    coe = rq1.consequence_of_error()
    tc = rq1.with_coe(tr, coe)
    res = upstream.estimate_h3(tc, indicator="coe")
    records = _rq1_part("R27", "coe", tc, res, extra=("indicator=coe",))
    socs = set(tr.rows["soc6"].to_list())
    missing = len(socs - set(coe.drop_nulls("coe")["soc6"].to_list()))
    notes = [
        "[default] H3 with the O*NET 29.3 Work Context element Consequence of Error (`CX`, the "
        "mean `Data Value` over the O*NET-SOC codes within soc6) in place of the D15 indicator, "
        "z-scored across the distinct soc6 codes of the H3 rows that have a value (population "
        "SD), so γ is in pp of validation share per 1 SD (PAP §8.2 R27, §11 C-58). Rows without "
        "a value are dropped and reported as `missing_coe`.",
        f"{missing} of the {len(socs)} soc6 codes of the H3 rows have no Consequence of Error "
        "value.",
        _rq1_note("pp of validation share per 1 SD of Consequence of Error"),
    ]
    return _write("R27", records, notes, out_dir)


def run_R31(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R31: H3 with H1's covariates (education, log wage) added (P13)."""
    guards.require_rq1_run_committed()
    tr = upstream.task_rows()
    res = upstream.estimate_h3(tr, covariates=H1_COVARIATES)
    records = _rq1_part(
        "R31", "covariates", tr, res, extra=(f"covariates={', '.join(H1_COVARIATES)}",)
    )
    notes = [
        "H3 with H1's covariates `human_education_years_mean` and `log_wage` added (PAP §8.2 "
        "R31, P13); the H3 sample then requires both covariates (Plan 2's drop rule on the "
        "estimator's own variables, PAP §11 C-12). The non-PSD rule is applied to γ's block "
        "alone and the covariate coefficients come from a second call on the same design, so "
        "the covariates never change γ's inference (PAP §11 C-14).",
        _rq1_note(),
    ]
    return _write("R31", records, notes, out_dir)


def run_R38(*, out_dir: Path | None = None) -> tuple[Path, Path]:
    """PAP §8.2 R38: H1 and H3 with SEs clustered by occupation only (spec §5.2, P18)."""
    guards.require_rq1_run_committed()
    tr = upstream.task_rows()
    kw = {"extra": ("se=oneway_occ",), "se_key": "se_oneway_occ"}
    records = [
        *_rq1_part("R38", "oneway_occ", tr, upstream.estimate_h1(tr), **kw),
        *_rq1_part("R38", "oneway_occ", tr, upstream.estimate_h3(tr), **kw),
    ]
    notes = [
        "SEs clustered by occupation (soc6) only, the spec's §5.2 rule (PAP §4 departure, §8.2 "
        "R38, P18): SE and p are Plan 2's one-way diagnostics `se_oneway_occ` / `p_oneway_occ` "
        "of the primary H1 and H3 fits, df = G_occ − 1, interval estimate ± t(0.975, G_occ − "
        "1)·SE; point estimates are the primary ones. p_H1 is D17's max of the two one-way "
        "p-values. Reported only; used in no decision.",
        _rq1_note(),
    ]
    return _write("R38", records, notes, out_dir)


RUNNERS: dict[str, Callable[..., tuple[Path, Path]]] = {
    rid: fn
    for rid, fn in (
        ("R1", run_R01),
        ("R2", run_R02),
        ("R3", run_R03),
        ("R11", run_R11),
        ("R14", run_R14),
        ("R15", run_R15),
        ("R17", run_R17),
        ("R20", run_R20),
        ("R33", run_R33),
        ("R5", run_R05),
        ("R7", run_R07),
        ("R10", run_R10),
        ("R18", run_R18),
        ("R19", run_R19),
        ("R21", run_R21),
        ("R34", run_R34),
        ("R35", run_R35),
        ("R6", run_R06),
        ("R32", run_R32),
        ("R4", run_R04),
        ("R8", run_R08),
        ("R9", run_R09),
        ("R16", run_R16),
        ("R23", run_R23),
        ("R24", run_R24),
        ("R26", run_R26),
        ("R27", run_R27),
        ("R31", run_R31),
        ("R38", run_R38),
    )
}
