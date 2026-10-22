"""Occupation and Fama-French 49 exposure indices (spec section 5.3).

AEI data are conversations matched to O*NET tasks. An exposure score here measures how
much of the conversations matched to an occupation's (or an industry's occupations') tasks
there are, relative to that occupation's share of employment, and which collaboration
pattern they show. It says nothing about job risk or displacement in the labour market.

Occupation level (`occupation_exposure`)
- AEI soc6 codes are mapped to OEWS codes with `oews_code_for` (exact, broad-group rollup,
  or a unique OEWS hybrid). The map is many-to-one, so `usage_share` is SUMMED by OEWS code,
  and each pattern share is the usage-weighted mean over the AEI codes with a non-null
  value. Usage on AEI codes with no OEWS code is dropped and the remainder renormalised to
  100 (`oews_usage` reports the dropped share; it is 0 for r2).
- `emp_share` is the occupation's share of national detailed-occupation employment, May 2024
  OEWS (occupations with suppressed `tot_emp` are left out of the denominator and the output).
- `U = usage_share / (100 * emp_share)`; `D = U * automation_pct / 100`;
  `A = U * augmentation_pct / 100`; `D_lb`, `D_ub` use `automation_share_all_lb` / `_ub`
  (controller ruling R7: suppressed conversations counted as non-automation / automation)
  in place of `automation_pct`. The pre-analysis plan picks the primary delegation measure.
- An occupation with usage but a null pattern share gets that measure null; it drops out of
  the industry sums for that measure (weights renormalised) and lowers `emp_covered_share`.
- `unmatched="zero"` (default) is an ASSUMPTION: an OEWS occupation with no AEI usage
  (12.1% of May 2024 employment for r2, 6.3% pooled; mostly manual trades) is unpublished,
  not measured zero, but is given `U = D = A = D_lb = D_ub = 0` (`has_usage = False`).
  `unmatched="drop"` removes those occupations instead, so they leave the
  industry sums like a null measure (robustness).

Industry level (`aggregate_to_ff49`, `industry_exposure`)
- Within an OEWS industry code, `E = sum_o w_o X_o / sum_o w_o` over occupations with a
  non-null `X`, `w_o` = `emp_share_in_industry`. The industry's coverage for `X` is
  `sum_o w_o` over those occupations.
- An OEWS code's FF49 weights come from the crosswalk exactly as in
  `aideleg.crosswalk.naics_ff49` (padded codes, letter aggregates). FF49 `E` is the mean of
  the codes' `E` weighted by crosswalk weight x code employment, over codes with a non-null
  `E`; FF49 coverage is the same-weighted mean of the codes' coverage (codes with no
  coverage count as 0). Only `private` codes with a non-null FF49 enter: government
  (99xxxx, USPS 491100) and, under `hq="exclude"`, NAICS 5511 are left out.
- `emp_covered_share` is the coverage of `D` (the primary delegation measure). It reflects
  only the loss to null pattern shares (and suppressed OEWS employment); under
  `unmatched="zero"` the zero-assigned occupations count as covered. `z_*` are
  standardised across the FF49 industries present, population SD (`ddof=0`).

Designs (`build_exposure`, `build_occupation_exposure`)
- `"B"`: release r2 only (confirmatory input). Only r2 rows of the panel are read.
- `"A_r2"`: identical numbers, labelled for the exploratory design.
- `"A_pooled"` (exploratory, ruling R5): `usage_share`, `automation_pct` and
  `augmentation_pct` averaged over r2-r6 with equal release weights; r6's two monthly
  periods are averaged first. `source == "claude_ai"` throughout. Within an average, an
  occupation absent from a period or release counts as `usage_share = 0` (the shares keep
  summing to 100) and pattern shares average over the periods/releases that publish them.
  The R7 bounds are not definition-stable across releases, so `D_lb` / `D_ub` are null.
  Every release r2-r6 must be present (else ValueError; `allow_missing=True` is for toy
  inputs). Basis change: r6 uses the published SOC basis, and 43 occupations appear only in
  r6 (claude_ai), carrying 1.77% of r6 usage (e.g. 25-3031 at 1.36%); they enter A_pooled
  through r6 alone.
Every output carries `design` and `exploratory` columns.
"""

import sys
from typing import Literal

import polars as pl

from aideleg.bls.oews import oews_code_for
from aideleg.occupations import KEY, occupation_table

Design = Literal["B", "A_pooled", "A_r2"]
DESIGNS: tuple[str, ...] = ("B", "A_pooled", "A_r2")
SOURCE = "claude_ai"
POOLED_RELEASES = ("r2", "r3", "r4", "r5", "r6")
SHARES = ["automation_pct", "augmentation_pct", "automation_share_all_lb",
          "automation_share_all_ub"]
# occupation measure -> (share column it scales U by, industry name)
MEASURES = {"U": (None, "usage"), "D": ("automation_pct", "delegation"),
            "A": ("augmentation_pct", "augmentation"),
            "D_lb": ("automation_share_all_lb", "delegation_lb"),
            "D_ub": ("automation_share_all_ub", "delegation_ub")}
OCC_COLUMNS = ["soc6", "title", "tot_emp", "emp_share", "has_usage", "usage_share", *SHARES,
               *MEASURES]
FF49_COLUMNS = (["ff49", "ff49_short"] + [f"E_{n}" for _, n in MEASURES.values()]
                + [f"z_{n}" for _, n in MEASURES.values()] + ["emp_covered_share", "emp"])


class _Default:
    def __repr__(self) -> str:
        return "DEFAULT"


DEFAULT = _Default()  # "load the study input" for keyword arguments where None means "none"


def _wmean(col: str, w: str = "usage_share") -> pl.Expr:
    has = pl.col(col).is_not_null()
    den = pl.col(w).filter(has).sum()
    return pl.when(den > 0).then((pl.col(w) * pl.col(col)).filter(has).sum() / den).alias(col)


def _with_shares(occ: pl.DataFrame) -> pl.DataFrame:
    return occ.with_columns(pl.lit(None, pl.Float64).alias(c) for c in SHARES
                            if c not in occ.columns)


def oews_usage(occ: pl.DataFrame, national: pl.DataFrame,
               soc_structure: pl.DataFrame | None = None) -> tuple[pl.DataFrame, float]:
    """AEI occupation rows summed to OEWS codes: (`soc6` = OEWS code, `usage_share`, SHARES),
    and the percent of usage on AEI codes with no OEWS code (dropped before renormalising)."""
    if occ["soc6"].is_duplicated().any():
        raise ValueError("occ must hold one row per soc6 (one release, period and source)")
    if all(c in occ.columns for c in KEY) and occ.select(KEY).unique().height > 1:
        raise ValueError("occ spans more than one (release, period_start, source) key")
    codes = set(national.filter(pl.col("tot_emp").is_not_null())["soc6"])
    occ = _with_shares(occ).with_columns(
        oews=pl.col("soc6").map_elements(lambda s: oews_code_for(s, codes, soc_structure),
                                         return_dtype=pl.String))
    total = occ["usage_share"].sum()
    lost = occ.filter(pl.col("oews").is_null())["usage_share"].sum()
    mapped = (occ.filter(pl.col("oews").is_not_null())
              .group_by("oews").agg(pl.col("usage_share").sum(), *[_wmean(c) for c in SHARES])
              .rename({"oews": "soc6"}))
    kept = total - lost
    mapped = mapped.with_columns(
        usage_share=pl.col("usage_share") / kept * 100 if kept > 0 else pl.col("usage_share"))
    return mapped.sort("soc6"), (lost / total * 100 if total else 0.0)


def occupation_exposure(occ: pl.DataFrame, national: pl.DataFrame,
                        unmatched: Literal["zero", "drop"] = "zero", *,
                        soc_structure: pl.DataFrame | None = None) -> pl.DataFrame:
    """Per OEWS detailed occupation: `OCC_COLUMNS` (`U`, `D`, `A`, `D_lb`, `D_ub`, ...).

    `occ` is one key of `occupation_table` (or any frame with `soc6`, `usage_share` summing to
    100, and pattern shares in percent). `national` is `load_national`'s output. `unmatched`:
    see the module docstring; `"zero"` ASSUMES an occupation with no AEI usage has zero
    usage, although AEI leaves it unpublished.
    """
    if unmatched not in ("zero", "drop"):
        raise ValueError(f"unmatched must be 'zero' or 'drop', not {unmatched!r}")
    provided = {c for c in SHARES if c in occ.columns}
    use, _ = oews_usage(occ, national, soc_structure)
    nat = (national.filter(pl.col("tot_emp").is_not_null())
           .select("soc6", "title", "tot_emp")
           .with_columns(emp_share=pl.col("tot_emp") / pl.col("tot_emp").sum()))
    out = nat.join(use, on="soc6", how="left").with_columns(
        has_usage=pl.col("usage_share").is_not_null())
    if unmatched == "drop":
        out = out.filter(pl.col("has_usage"))
    u = pl.col("usage_share") / (100 * pl.col("emp_share"))
    exprs = []
    for name, (share, _) in MEASURES.items():
        x = u if share is None else u * pl.col(share) / 100
        if share is None or share in provided:
            x = pl.when(pl.col("has_usage")).then(x).otherwise(0.0)
        else:
            x = pl.lit(None, pl.Float64)  # never supplied: null everywhere, not zero
        exprs.append(x.alias(name))
    out = out.with_columns(exprs).with_columns(
        pl.when(pl.col("has_usage")).then(pl.col("usage_share")).otherwise(0.0)
        .alias("usage_share"))
    return out.select(OCC_COLUMNS).sort("soc6")


def _hq(crosswalk: pl.DataFrame) -> Literal["exclude", "redistribute"]:
    from aideleg.crosswalk.naics_ff49 import HQ_NAICS

    return ("redistribute" if crosswalk["naics"].str.starts_with(HQ_NAICS).any()
            else "exclude")


def aggregate_to_ff49(occ_values: pl.DataFrame, value_cols: list[str], matrix: pl.DataFrame,
                      crosswalk: pl.DataFrame) -> pl.DataFrame:
    """Occupation values -> FF49: `ff49, emp, <col>, <col>_covered` for each value column.

    `occ_values`: `soc6` (OEWS codes) and `value_cols`. `matrix`: `load_industry_matrix`'s
    output. `crosswalk`: `naics_to_ff49(..., digits=4)`'s output (5511 rows present means
    `hq="redistribute"`). `emp` is the FF49 industry's mapped private employment. See the
    module docstring for the weights and the coverage definition.
    """
    from aideleg.crosswalk.naics_ff49 import _oews_ff49

    long = (_oews_ff49(matrix, crosswalk, _hq(crosswalk))
            .filter((pl.col("status") == "private") & pl.col("ff49").is_not_null())
            .select("naics", "ff49", "emp"))
    w = pl.col("emp_share_in_industry")
    rows = matrix.select("naics", "soc6", "emp_share_in_industry").join(
        occ_values.select("soc6", *value_cols), on="soc6", how="left")
    per_code = []
    for c in value_cols:
        has = pl.col(c).is_not_null() & w.is_not_null()
        cov = w.filter(has).sum()
        per_code += [pl.when(cov > 0).then((w * pl.col(c)).filter(has).sum() / cov).alias(c),
                     cov.alias(f"{c}_covered")]
    by_code = rows.group_by("naics").agg(per_code)
    j = long.join(by_code, on="naics", how="left")
    aggs = [pl.col("emp").sum()]
    for c in value_cols:
        has = pl.col(c).is_not_null()
        den = pl.col("emp").filter(has).sum()
        aggs += [pl.when(den > 0).then((pl.col("emp") * pl.col(c)).filter(has).sum() / den)
                 .alias(c),
                 ((pl.col("emp") * pl.col(f"{c}_covered").fill_null(0.0)).sum()
                  / pl.col("emp").sum()).alias(f"{c}_covered")]
    return j.group_by("ff49").agg(aggs).sort("ff49")


def _z(col: str) -> pl.Expr:
    return (pl.col(col) - pl.col(col).mean()) / pl.col(col).std(ddof=0)


def _names() -> pl.DataFrame:
    from aideleg.crosswalk.naics_ff49 import _siccodes

    return _siccodes().select("ff49", "ff49_short").unique().sort("ff49")


def industry_exposure(occ_exp: pl.DataFrame, matrix: pl.DataFrame, crosswalk: pl.DataFrame,
                      *, names: pl.DataFrame | None = None) -> pl.DataFrame:
    """FF49 exposure: `FF49_COLUMNS`. `names` (`ff49, ff49_short`) defaults to Siccodes49."""
    agg = aggregate_to_ff49(occ_exp, list(MEASURES), matrix, crosswalk)
    out = agg.select(
        "ff49", "emp",
        *[pl.col(m).alias(f"E_{n}") for m, (_, n) in MEASURES.items()],
        emp_covered_share=pl.col("D_covered"),
    ).with_columns(_z(f"E_{n}").alias(f"z_{n}") for _, n in MEASURES.values())
    names = _names() if names is None else names
    return out.join(names.select("ff49", "ff49_short"), on="ff49", how="left").select(
        FF49_COLUMNS).sort("ff49")


def _release_occ(panel: pl.DataFrame, release: str, index) -> pl.DataFrame:
    sub = panel.filter(pl.col("release") == release)
    if sub.is_empty():
        return pl.DataFrame()
    return occupation_table(sub, release, index).filter(pl.col("source") == SOURCE)


def _average(frames: list[pl.DataFrame], by: str) -> pl.DataFrame:
    """Equal-weight mean of `usage_share` (absent = 0) and pattern shares (non-null only)."""
    stacked = pl.concat([f.select("soc6", "usage_share", "automation_pct", "augmentation_pct")
                         .with_columns(pl.lit(i).alias(by)) for i, f in enumerate(frames)])
    n = len(frames)
    return stacked.group_by("soc6").agg(
        usage_share=pl.col("usage_share").sum() / n,
        automation_pct=pl.col("automation_pct").mean(),
        augmentation_pct=pl.col("augmentation_pct").mean(),
    ).sort("soc6")


def design_occupations(design: Design, panel: pl.DataFrame, index, *,
                       allow_missing: bool = False) -> pl.DataFrame:
    """The AEI occupation table a design is built from (one row per AEI soc6).

    A_pooled raises unless every release in `POOLED_RELEASES` has claude_ai rows;
    `allow_missing=True` (toy inputs only) pools over the releases present instead.
    """
    if design in ("B", "A_r2"):
        occ = _release_occ(panel, "r2", index)
        if occ.is_empty() or occ.select(KEY).unique().height != 1:
            raise ValueError("expected exactly one r2 claude_ai period")
        return occ
    if design == "A_pooled":
        per_release, missing = [], []
        for r in POOLED_RELEASES:
            t = _release_occ(panel, r, index)
            if t.is_empty():
                missing.append(r)
                continue
            periods = [t.filter(pl.col("period_start") == p)
                       for p in sorted(t["period_start"].unique())]
            per_release.append(_average(periods, "period") if len(periods) > 1 else t)
        if missing and not allow_missing:
            raise ValueError(f"A_pooled needs claude_ai rows for every release in "
                             f"{POOLED_RELEASES}; missing {missing}")
        if not per_release:
            raise ValueError("no r2-r6 claude_ai rows in the panel")
        return _average(per_release, "release")
    raise ValueError(f"design must be one of {DESIGNS}, not {design!r}")


def _inputs(panel, index, national, soc_structure):
    from aideleg.acquire.sources import by_key
    from aideleg.aei.tasks import default_index
    from aideleg.bls.oews import load_national
    from aideleg.config import DERIVED, RAW

    if panel is None:
        panel = pl.read_parquet(DERIVED / "aei_panel.parquet")
    index = default_index() if index is None else index
    national = load_national(2024) if national is None else national
    if soc_structure is DEFAULT:
        soc_structure = pl.read_csv(RAW / by_key("aei_soc_structure").dest)
    return panel, index, national, soc_structure


def _label(df: pl.DataFrame, design: str) -> pl.DataFrame:
    return df.with_columns(design=pl.lit(design), exploratory=pl.lit(design != "B"))


def build_occupation_exposure(design: Design, *, panel=None, index=None, national=None,
                              soc_structure=DEFAULT,
                              unmatched: Literal["zero", "drop"] = "zero",
                              allow_missing: bool = False) -> pl.DataFrame:
    """`occupation_exposure` for a design, with `design` and `exploratory` columns. Inputs
    default to the study data (panel, `default_index()`, May 2024 OEWS, AEI SOC structure);
    `soc_structure=None` disables OEWS hybrid matching."""
    if design not in DESIGNS:
        raise ValueError(f"design must be one of {DESIGNS}, not {design!r}")
    panel, index, national, soc_structure = _inputs(panel, index, national, soc_structure)
    occ = design_occupations(design, panel, index, allow_missing=allow_missing)
    return _label(occupation_exposure(occ, national, unmatched, soc_structure=soc_structure),
                  design)


def build_exposure(design: Design, *, panel=None, index=None, national=None, matrix=None,
                   crosswalk=None, names=None, soc_structure=DEFAULT,
                   unmatched: Literal["zero", "drop"] = "zero",
                   allow_missing: bool = False) -> pl.DataFrame:
    """FF49 exposure for a design (`FF49_COLUMNS` + `design`, `exploratory`). Defaults: the
    study inputs, `load_industry_matrix(2024, 4)` and `naics_to_ff49("split", 4, "exclude")`."""
    occ = build_occupation_exposure(design, panel=panel, index=index, national=national,
                                    soc_structure=soc_structure, unmatched=unmatched,
                                    allow_missing=allow_missing)
    if matrix is None:
        from aideleg.bls.oews import load_industry_matrix

        matrix = load_industry_matrix(2024, 4)
    if crosswalk is None:
        from aideleg.crosswalk.naics_ff49 import naics_to_ff49

        crosswalk = naics_to_ff49("split", 4, "exclude")
    ind = industry_exposure(occ.drop("design", "exploratory"), matrix, crosswalk, names=names)
    return _label(ind, design)


def main() -> int:
    from aideleg.bls.oews import load_industry_matrix
    from aideleg.config import DERIVED
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49

    panel, index, national, struct = _inputs(None, None, None, DEFAULT)
    matrix, xw = load_industry_matrix(2024, 4), naics_to_ff49("split", 4, "exclude")
    kw = dict(panel=panel, index=index, national=national, soc_structure=struct)
    occs, inds = [], []
    for d in DESIGNS:
        occ = build_occupation_exposure(d, **kw)
        ind = _label(industry_exposure(occ.drop("design", "exploratory"), matrix, xw), d)
        _, lost = oews_usage(design_occupations(d, panel, index), national, struct)
        cov = occ.filter("has_usage")["tot_emp"].sum() / occ["tot_emp"].sum()
        print(f"[{d}] {occ.height} occupations ({cov:.1%} of employment with conversations "
              f"matched to their tasks; {lost:.2f}% of usage on AEI codes with no OEWS code); "
              f"{ind.height} FF49 industries; emp_covered_share "
              f"{ind['emp_covered_share'].min():.3f}-{ind['emp_covered_share'].max():.3f}")
        occs.append(occ)
        inds.append(ind)
    DERIVED.mkdir(parents=True, exist_ok=True)
    pl.concat(occs).write_parquet(DERIVED / "exposure_occupation.parquet")
    pl.concat(inds).write_parquet(DERIVED / "exposure_ff49.parquet")
    b = inds[0].sort("z_delegation", descending=True).select(
        "ff49", "ff49_short", "z_delegation", "z_usage", "emp_covered_share")
    with pl.Config(tbl_rows=12, float_precision=3):
        print("Design B, top 5 FF49 by z_delegation (descriptive):", b.head(5), sep="\n")
        print("Design B, bottom 5 FF49 by z_delegation (descriptive):", b.tail(5), sep="\n")
    print("-> data/derived/exposure_occupation.parquet, data/derived/exposure_ff49.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
