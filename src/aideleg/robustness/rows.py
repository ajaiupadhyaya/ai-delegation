"""The PAP §8.2 robustness row runners (Plan 4). Each `run_R<nn>()` writes
`docs/results/robustness/R<nn>.csv` and `.md` through `report.write_row` and returns their paths.

Exposure-construction rows (Task 7): R1, R2, R3, R11, R14, R15, R17, R20, R33. Each rebuilds
the Design B exposure under one fixed `ExposureSpec` and writes up to two parts:

- `market`: H5 and H5b through `market.market_variant` on `ff49_vw`, with s, b-bar and q
  recomputed for the variant's exposure vector on the 378 pre-seal windows (PAP §3.3, §8.1, D21);
- `rq2`: Plan 2's could-vs-does Spearman table (`upstream.rq2_correlations`) of the variant
  indices against the variant benchmarks, with Plan 2's Design B bootstrap draws (C-68).

Every record is reported as robustness; no row changes a confirmatory decision (PAP §8.1).
AEI data are conversations matched to O*NET tasks.
"""

from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path

import polars as pl

from aideleg.robustness import registry, report
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
    )
}
