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

Every record is reported as robustness; no row changes a confirmatory decision (PAP §8.1).
AEI data are conversations matched to O*NET tasks.
"""

from collections.abc import Callable
from dataclasses import dataclass, field, fields
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl

from aideleg import confirm_h5, power
from aideleg.robustness import market, registry, report, returns, studentised
from aideleg.robustness.exposure_variants import (
    ZERO_ASSIGNED_NOTE,
    ExposureSpec,
    variant_exposure,
    zero_assigned_share,
)
from aideleg.robustness.market import market_variant
from aideleg.robustness.upstream import AEI_COLS, BENCH_COLS, rq2_correlations

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
    "In the confirmatory window SE_Σ is computed the same way; stat = T_stud = (b̂ − b₀)/(κ·SE_Σ) "
    "with b₀ = b̄ (D21), p from t₂₁, and the t₂₁ criticals of §3.3. The scale column is κ·SE_Σ "
    "in pp and the interval is b̂ ± t₂₁,0.975·κ·SE_Σ (the §3.3 interval form with this scale).",
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
                f"returns={rs}; z=z_delegation; control={control}; statistic=T_stud; criticals=t21"
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


run_R05 = _market_runner("R5")
run_R07 = _market_runner("R7")
run_R10 = _market_runner("R10")
run_R18 = _market_runner("R18")
run_R19 = _market_runner("R19")
run_R21 = _market_runner("R21")
run_R34 = _market_runner("R34")

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
    )
}
