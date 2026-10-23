"""Exposure variants for the PAP §8.2 rows that rebuild an exposure index (Plan 4 Tasks 5-6).

AEI data are conversations matched to O*NET tasks. A variant index measures the same thing
as the primary one under a different, pre-specified construction. The study's one
disclaimer is `aideleg.results.common.WORDING`.

`ExposureSpec()` is the primary Design B construction, and `variant_exposure(ExposureSpec())`
reproduces the frozen vector (PAP §9.3). Each option maps onto an existing parameter:

| option | rows | existing parameter |
|---|---|---|
| `design` | (R4, R16) | `exposure.design_occupations` logic; A_pooled is the `_average` pool |
| `oews_year` | R1, R32 | `load_national(year)`, `load_industry_matrix(year, 4)` |
| `weights="wage_bill"` | R2 | `inputs.wage_bill_matrix` (the matrix only; U_o keeps employment) |
| `unmatched` | R3 | `occupation_exposure(unmatched=)` |
| `allocation="employment"` | R11 | `inputs.employment_allocation_table` (task-basis tables) |
| `crosswalk` | R20, R33 | `naics_to_ff49(method=)`; `inputs.emp_weighted_naics_ff49` |
| `hq` | R15 | `naics_to_ff49(hq=, employment=<variant matrix>)` |
| `industries` | R6 | `naics_to_ff49(siccodes_key=)`, names from that Siccodes file |
| `source="1p_api"` | R4 | the A_pooled pool over r3-r6 (Design B has no API source) |
| `r6_basis="tasks"` | R16 | `occupation_table(..., basis="tasks")` for r6 in the pool |
| `onet="29.2"` | R32 | `inputs.index_29_2` |
| `aioe_crosswalk="bls"` | R14 | `inputs.bls_soc_crosswalk` into `load_aioe(crosswalk=)` |

Benchmarks (PAP §11 C-65, [default]): AIOE and Eloundou are re-aggregated with the variant's
matrix, crosswalk and industry set (`benchmark_ff49(occ_values=, matrix=, crosswalk=)`), and
mapped to the variant year's OEWS codes, so both sides of H5b use the same weights. The
occupation-level options (R3, R11, R16) leave the benchmark at its primary value because they
change neither the matrix nor the crosswalk. R14 replaces AIOE itself.

Every exposure row states its zero-assigned employment share (D3), `zero_assigned_share`,
formatted with `ZERO_ASSIGNED_NOTE`. Nothing here writes to `data/derived/`.
"""

import hashlib
from dataclasses import dataclass
from functools import cache
from typing import Literal

import polars as pl

from aideleg import audit
from aideleg.exposure import _average, industry_exposure, occupation_exposure
from aideleg.occupations import KEY, occupation_table

ZERO_ASSIGNED_NOTE = "Zero-assigned employment share (D3): {:.2f}%"
POOLS: dict[str, tuple[str, ...]] = {
    "claude_ai": ("r2", "r3", "r4", "r5", "r6"),  # exposure.POOLED_RELEASES (ruling R5)
    "1p_api": ("r3", "r4", "r5", "r6"),  # PAP R4: the API source starts at r3
}
OUT_COLUMNS = [
    "industry",
    "industry_short",
    "z_usage",
    "z_delegation",
    "z_augmentation",
    "z_delegation_lb",
    "z_delegation_ub",
    "z_aioe",
    "z_eloundou",
    "z_eloundou_gpt4",
    "emp_covered_share",
]


@dataclass(frozen=True)
class ExposureSpec:
    """One exposure construction. The defaults are the primary (Design B, PAP §2)."""

    design: Literal["B", "A_pooled"] = "B"
    oews_year: Literal[2023, 2024, 2025] = 2024
    weights: Literal["employment", "wage_bill"] = "employment"
    unmatched: Literal["zero", "drop"] = "zero"
    allocation: Literal["equal", "employment"] = "equal"
    crosswalk: Literal["split", "majority", "emp_weighted"] = "split"
    hq: Literal["exclude", "redistribute"] = "exclude"
    industries: Literal[49, 30, 48] = 49
    source: Literal["claude_ai", "1p_api"] = "claude_ai"
    r6_basis: Literal["auto", "tasks"] = "auto"
    onet: Literal["29.3", "29.2"] = "29.3"
    aioe_crosswalk: Literal["onet_union", "bls"] = "onet_union"

    def __post_init__(self) -> None:
        allowed = {
            "design": ("B", "A_pooled"),
            "oews_year": (2023, 2024, 2025),
            "weights": ("employment", "wage_bill"),
            "unmatched": ("zero", "drop"),
            "allocation": ("equal", "employment"),
            "crosswalk": ("split", "majority", "emp_weighted"),
            "hq": ("exclude", "redistribute"),
            "industries": (49, 30, 48),
            "source": ("claude_ai", "1p_api"),
            "r6_basis": ("auto", "tasks"),
            "onet": ("29.3", "29.2"),
            "aioe_crosswalk": ("onet_union", "bls"),
        }
        for name, ok in allowed.items():
            if getattr(self, name) not in ok:
                raise ValueError(f"{name} must be one of {ok}, not {getattr(self, name)!r}")


# --- Task 6 constructions (`aideleg.robustness.inputs`) ---------------------------------


def _wage_bill_matrix(year: int) -> pl.DataFrame:
    """R2 (C-66): the wage-bill matrix replaces employment in the industry weights only."""
    from aideleg.robustness.inputs import wage_bill_matrix

    return wage_bill_matrix(year)


def _employment_allocation_table(
    panel: pl.DataFrame, release: str, index, national: pl.DataFrame
) -> pl.DataFrame:
    """R11 (D4 alternative), task-basis tables only; `_release_table` keeps r6's published SOC
    rows as published. Employment is the spec year's national `tot_emp`."""
    from aideleg.robustness.inputs import employment_allocation_table

    return employment_allocation_table(panel, release, index, national, soc_structure=_structure())


def _emp_weighted_naics_ff49(siccodes_key: str) -> pl.DataFrame:
    """R33 (C-67)."""
    from aideleg.robustness.inputs import emp_weighted_naics_ff49

    return emp_weighted_naics_ff49(siccodes_key)


def _bls_soc_crosswalk() -> pl.DataFrame:
    """R14 (D6 alternative)."""
    from aideleg.robustness.inputs import bls_soc_crosswalk

    return bls_soc_crosswalk()


def _index_29_2():
    """R32: O*NET 29.2 task statements."""
    from aideleg.robustness.inputs import index_29_2

    return index_29_2()


# --- inputs -------------------------------------------------------------------------------


@cache
def _panel() -> pl.DataFrame:
    from aideleg.config import DERIVED

    return pl.read_parquet(DERIVED / "aei_panel.parquet")


@cache
def _structure() -> pl.DataFrame:
    from aideleg.acquire.sources import by_key
    from aideleg.config import RAW

    return pl.read_csv(RAW / by_key("aei_soc_structure").dest)


@cache
def _national(year: int) -> pl.DataFrame:
    from aideleg.bls.oews import load_national

    return load_national(year)


@cache
def _matrix(year: int, weights: str) -> pl.DataFrame:
    from aideleg.bls.oews import load_industry_matrix

    return load_industry_matrix(year, 4) if weights == "employment" else _wage_bill_matrix(year)


def _index(onet: str):
    from aideleg.aei.tasks import default_index

    return default_index() if onet == "29.3" else _index_29_2()


def _siccodes_key(industries: int) -> str:
    return f"ff_siccodes{industries}"


@cache
def _crosswalk(spec: ExposureSpec) -> pl.DataFrame:
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49

    key = _siccodes_key(spec.industries)
    if spec.crosswalk == "emp_weighted":
        if spec.hq == "redistribute":
            raise NotImplementedError("crosswalk='emp_weighted' with hq='redistribute'")
        return _emp_weighted_naics_ff49(key)
    return naics_to_ff49(
        spec.crosswalk,
        4,
        spec.hq,
        siccodes_key=key,
        employment=_matrix(spec.oews_year, spec.weights),
    )


def _names(industries: int) -> pl.DataFrame:
    from aideleg.crosswalk.naics_ff49 import _siccodes

    return _siccodes(_siccodes_key(industries)).select("ff49", "ff49_short").unique().sort("ff49")


# --- occupations --------------------------------------------------------------------------


def _check(spec: ExposureSpec) -> None:
    if spec.design == "B" and spec.source != "claude_ai":
        raise ValueError("Design B has no 1p_api source (PAP R4): use design='A_pooled'")
    if spec.design == "B" and spec.r6_basis != "auto":
        raise ValueError("r6_basis applies to A_pooled only: Design B reads r2 alone")


def _release_table(
    spec: ExposureSpec, panel: pl.DataFrame, release: str, index, national: pl.DataFrame
) -> pl.DataFrame:
    """One release's occupation table for the spec's source (empty frame if none)."""
    sub = panel.filter(pl.col("release") == release)
    if sub.is_empty():
        return pl.DataFrame()
    basis = "tasks" if (release == "r6" and spec.r6_basis == "tasks") else "auto"
    published = basis == "auto" and release == "r6"
    if spec.allocation == "employment" and not published:
        t = _employment_allocation_table(sub, release, index, national)
    else:
        t = occupation_table(sub, release, index, basis=basis)
    return t.filter(pl.col("source") == spec.source)


def _design_occupations(spec: ExposureSpec, national: pl.DataFrame) -> pl.DataFrame:
    """As `exposure.design_occupations`, with the spec's source, r6 basis, allocation, index."""
    panel, index = _panel(), _index(spec.onet)
    if spec.design == "B":
        occ = _release_table(spec, panel, "r2", index, national)
        if occ.is_empty() or occ.select(KEY).unique().height != 1:
            raise ValueError("expected exactly one r2 claude_ai period")
        return occ
    per_release, missing = [], []
    for r in POOLS[spec.source]:
        t = _release_table(spec, panel, r, index, national)
        if t.is_empty():
            missing.append(r)
            continue
        periods = [
            t.filter(pl.col("period_start") == p) for p in sorted(t["period_start"].unique())
        ]
        per_release.append(_average(periods, "period") if len(periods) > 1 else t)
    if missing:
        raise ValueError(
            f"A_pooled ({spec.source}) needs every release in "
            f"{POOLS[spec.source]}; missing {missing}"
        )
    return _average(per_release, "release")


@cache
def _variant_occupations(spec: ExposureSpec) -> pl.DataFrame:
    _check(spec)
    national = _national(spec.oews_year)
    occ = _design_occupations(spec, national)
    out = occupation_exposure(occ, national, spec.unmatched, soc_structure=_structure())
    return out.with_columns(design=pl.lit(spec.design))


def variant_occupations(spec: ExposureSpec) -> pl.DataFrame:
    """The variant's occupation-level exposure (`exposure.OCC_COLUMNS` + `design`)."""
    return _variant_occupations(spec)


def zero_assigned_share(spec: ExposureSpec) -> float:
    """Percent of the variant's OEWS employment assigned zero usage (D3), from
    `audit.design_zero_assigned`. Under `unmatched="drop"` it is 0 (they are dropped)."""
    z = audit.design_zero_assigned(variant_occupations(spec))
    return float(z.filter(pl.col("design") == spec.design)["no_usage_emp_pct"].item())


# --- industries ---------------------------------------------------------------------------


def _benchmark_occupations(spec: ExposureSpec) -> pl.DataFrame:
    from aideleg.benchmarks import benchmark_occupations, load_aioe, to_oews

    national = _national(spec.oews_year)
    occ = benchmark_occupations(national, _structure())
    if spec.aioe_crosswalk == "bls":  # R14: AIOE through the BLS SOC 2010 -> 2018 crosswalk
        codes = set(national.filter(pl.col("tot_emp").is_not_null())["soc6"])
        a = to_oews(load_aioe(_bls_soc_crosswalk()), ["aioe"], codes, _structure())
        occ = occ.drop("aioe").join(a, on="soc6", how="left").select(occ.columns)
    return occ


@cache
def _variant_exposure(spec: ExposureSpec) -> pl.DataFrame:
    from aideleg.benchmarks import benchmark_ff49

    occ = variant_occupations(spec).drop("design")
    matrix, xw = _matrix(spec.oews_year, spec.weights), _crosswalk(spec)
    ind = industry_exposure(occ, matrix, xw, names=_names(spec.industries))
    bench = benchmark_ff49(occ_values=_benchmark_occupations(spec), matrix=matrix, crosswalk=xw)
    out = ind.join(
        bench.select("ff49", "z_aioe", "z_eloundou", "z_eloundou_gpt4"), on="ff49", how="left"
    )
    return (
        out.rename({"ff49": "industry", "ff49_short": "industry_short"})
        .select(OUT_COLUMNS)
        .sort("industry")
    )


def variant_exposure(spec: ExposureSpec) -> pl.DataFrame:
    """Industry exposure for `spec`: `OUT_COLUMNS`, one row per industry present."""
    _check(spec)
    return _variant_exposure(spec)


def vector_hash(df: pl.DataFrame) -> str:
    """The PAP §9.3 vector hash of `(industry, industry_short, z_delegation, z_aioe)`, with the
    columns named `ff49`, `ff49_short` as in `confirm_h5._vector_hash`."""
    v = df.sort("industry").select(
        ff49="industry", ff49_short="industry_short", z_delegation="z_delegation", z_aioe="z_aioe"
    )
    return hashlib.sha256(v.write_csv(float_precision=10).encode()).hexdigest()
