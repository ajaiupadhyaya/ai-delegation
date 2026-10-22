"""Theoretical-exposure benchmarks aggregated to Fama-French 49 (spec RQ2, descriptive).

These are "could" measures: how much of an occupation's tasks or abilities a language model
could in principle perform. They are compared with the AEI indices ("does": conversations
matched to O*NET tasks) by rank correlation across FF49, with no hypothesis attached. Nothing
here says anything about job risk or displacement in the labour market.

Inputs (columns verified on the downloaded files, 2026-10-21)
- `aioe`, `AIOE_DataAppendix.xlsx` (Felten, Raj & Seamans 2021). Sheets: `Index`,
  `Appendix A` (occupation level: `SOC Code`, `Occupation Title`, `AIOE`; 774 rows, one per
  6-digit SOC code), `Appendix B` (AIIE by 4-digit NAICS), `Appendix C` (AIGE by FIPS),
  `Appendix D`/`E` (ability level). Only `Appendix A` is used.
  Vintage: SOC 2010 (88 of its 774 codes are not SOC 2018 detailed codes; all 774 are the
  first 7 characters of an O*NET-SOC 2010 code in the O*NET 2010 -> 2019 crosswalk).
- `eloundou_occ`, `occ_level.csv` (Eloundou, Manning, Mishkin & Rock, GPTs-are-GPTs):
  `O*NET-SOC Code, Title, dv_rating_{alpha,beta,gamma}, human_rating_{alpha,beta,gamma}`.
  923 rows = the O*NET-SOC 2019 taxonomy (SOC 2018 in the first 7 characters), so no
  vintage mapping is needed. `dv_rating_*` is the GPT-4 rating, `human_rating_*` the human
  one. Only beta (full exposure for tasks a model can speed up directly, half credit for
  tasks that need extra tooling) is used: `beta_human = human_rating_beta`,
  `beta_gpt4 = dv_rating_beta`. Several O*NET-SOC codes share one SOC code; they are averaged
  (simple mean) to `soc6`.

Vintage mapping (AIOE only), `map_soc2010_to_2018`
- A SOC 2010 code is looked up through the O*NET 2010 -> 2019 crosswalk (every O*NET-SOC 2010
  code whose first 7 characters equal it), giving its SOC 2018 successors (first 7 characters
  of the 2019 codes). A split gives each successor the same value. A merge (several 2010
  codes into one 2018 code) takes the SIMPLE mean of the 2010 values: 2010-vintage employment
  weights are not available, and this is a choice. A 2010 code absent from the crosswalk
  raises ValueError.

OEWS codes (`to_oews`)
- SOC 2018 codes are resolved with `oews_code_for` (exact, broad-group rollup, unique
  hybrid). Where several codes land on one OEWS code the values are averaged (simple mean).
  OEWS occupations with no benchmark value stay null (never zero); industry aggregation then
  renormalises over occupations with a value, and `<col>_covered` reports the share of
  industry employment that has one.

FF49 (`benchmark_ff49`): `aggregate_to_ff49` with `load_industry_matrix(2024, 4)` and
`naics_to_ff49("split", 4, "exclude")`, the AEI indices' weights; z-scores across the FF49
industries present, population SD. `z_eloundou` is the human-rated beta.
"""

import sys

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import DERIVED, RAW

SOC_RE = r"^\d{2}-\d{4}$"
AIOE_SHEET = "Appendix A"
AIOE_COLUMNS = ("SOC Code", "Occupation Title", "AIOE")


def load_aioe_raw() -> pl.DataFrame:
    """`soc6, aioe` on the SOC 2010 vintage, as published (774 rows)."""
    import openpyxl

    wb = openpyxl.load_workbook(RAW / by_key("aioe").dest, read_only=True, data_only=True)
    try:
        rows = list(wb[AIOE_SHEET].iter_rows(values_only=True))
    finally:
        wb.close()
    if tuple(rows[0]) != AIOE_COLUMNS:
        raise ValueError(f"{AIOE_SHEET} columns are {rows[0]}, expected {AIOE_COLUMNS}")
    df = pl.DataFrame([r[:3] for r in rows[1:] if r[0] is not None],
                      schema={"soc6": pl.String, "title": pl.String, "aioe": pl.Float64},
                      orient="row").select("soc6", "aioe")
    if not df["soc6"].str.contains(SOC_RE).all():
        raise ValueError("AIOE has SOC codes that are not NN-NNNN")
    return df


def _crosswalk() -> pl.DataFrame:
    path = RAW / by_key("onet_2010_2019_crosswalk").dest
    return pl.read_csv(path, columns=["O*NET-SOC 2010 Code", "O*NET-SOC 2019 Code"]).rename(
        {"O*NET-SOC 2010 Code": "o2010", "O*NET-SOC 2019 Code": "o2019"})


def map_soc2010_to_2018(df: pl.DataFrame, crosswalk: pl.DataFrame | None = None, *,
                        value_cols: list[str] | None = None) -> pl.DataFrame:
    """SOC 2010 `soc6` rows -> SOC 2018 `soc6` (splits copy, merges take the simple mean)."""
    cols = value_cols or [c for c in df.columns if c != "soc6"]
    xw = _crosswalk() if crosswalk is None else crosswalk
    pairs = (xw.select(old=pl.col("o2010").str.slice(0, 7), new=pl.col("o2019").str.slice(0, 7))
             .unique())
    lost = sorted(set(df["soc6"]) - set(pairs["old"]))
    if lost:
        raise ValueError(f"SOC 2010 codes absent from the O*NET crosswalk: {lost}")
    return (df.join(pairs, left_on="soc6", right_on="old")
            .group_by("new").agg(pl.col(c).mean() for c in cols)
            .rename({"new": "soc6"}).sort("soc6"))


def load_aioe(crosswalk: pl.DataFrame | None = None) -> pl.DataFrame:
    """`soc6, aioe` on the SOC 2018 vintage (see the module docstring)."""
    return map_soc2010_to_2018(load_aioe_raw(), crosswalk)


def load_eloundou() -> pl.DataFrame:
    """`soc6, beta_human, beta_gpt4`: O*NET-SOC 2019 rows averaged to SOC 2018 codes."""
    df = pl.read_csv(RAW / by_key("eloundou_occ").dest)
    need = {"O*NET-SOC Code", "human_rating_beta", "dv_rating_beta"}
    if not need <= set(df.columns):
        raise ValueError(f"occ_level.csv lacks {sorted(need - set(df.columns))}")
    return (df.select(soc6=pl.col("O*NET-SOC Code").str.slice(0, 7),
                      beta_human=pl.col("human_rating_beta"), beta_gpt4=pl.col("dv_rating_beta"))
            .group_by("soc6").agg(pl.col("beta_human").mean(), pl.col("beta_gpt4").mean())
            .sort("soc6"))


def to_oews(df: pl.DataFrame, value_cols: list[str], oews_codes: set[str],
            soc_structure: pl.DataFrame | None = None) -> pl.DataFrame:
    """SOC 2018 `soc6` -> OEWS code (`oews_code_for`), simple mean where codes share one."""
    from aideleg.bls.oews import oews_code_for

    return (df.with_columns(oews=pl.col("soc6").map_elements(
                lambda s: oews_code_for(s, oews_codes, soc_structure), return_dtype=pl.String))
            .filter(pl.col("oews").is_not_null())
            .group_by("oews").agg(pl.col(c).mean() for c in value_cols)
            .rename({"oews": "soc6"}).sort("soc6"))


def _structure() -> pl.DataFrame:
    return pl.read_csv(RAW / by_key("aei_soc_structure").dest)


def coverage(df: pl.DataFrame, national: pl.DataFrame, soc_structure=None) -> float:
    """Share of OEWS detailed-occupation employment on OEWS codes that `df` reaches."""
    nat = national.filter(pl.col("tot_emp").is_not_null())
    got = to_oews(df.select("soc6"), [], set(nat["soc6"]), soc_structure)
    hit = nat.filter(pl.col("soc6").is_in(got["soc6"].implode()))
    return hit["tot_emp"].sum() / nat["tot_emp"].sum()


def benchmark_occupations(national: pl.DataFrame | None = None, soc_structure=None
                          ) -> pl.DataFrame:
    """OEWS-coded benchmark values: `soc6, aioe, beta_human, beta_gpt4` (null = no value)."""
    from aideleg.bls.oews import load_national

    national = load_national(2024) if national is None else national
    codes = set(national.filter(pl.col("tot_emp").is_not_null())["soc6"])
    structure = _structure() if soc_structure is None else soc_structure
    a = to_oews(load_aioe(), ["aioe"], codes, structure)
    e = to_oews(load_eloundou(), ["beta_human", "beta_gpt4"], codes, structure)
    return pl.DataFrame({"soc6": sorted(codes)}).join(a, on="soc6", how="left").join(
        e, on="soc6", how="left")


def benchmark_ff49(*, occ_values: pl.DataFrame | None = None, matrix=None, crosswalk=None
                   ) -> pl.DataFrame:
    """`ff49, z_aioe, z_eloundou` then `z_eloundou_gpt4`, `E_*`, `<col>_covered`, `emp`."""
    from aideleg.bls.oews import load_industry_matrix
    from aideleg.crosswalk.naics_ff49 import naics_to_ff49
    from aideleg.exposure import _z, aggregate_to_ff49

    occ_values = benchmark_occupations() if occ_values is None else occ_values
    matrix = load_industry_matrix(2024, 4) if matrix is None else matrix
    crosswalk = naics_to_ff49("split", 4, "exclude") if crosswalk is None else crosswalk
    cols = ["aioe", "beta_human", "beta_gpt4"]
    agg = aggregate_to_ff49(occ_values, cols, matrix, crosswalk)
    out = agg.rename({"aioe": "E_aioe", "beta_human": "E_eloundou", "beta_gpt4": "E_eloundou_gpt4",
                      "aioe_covered": "aioe_covered", "beta_human_covered": "eloundou_covered",
                      "beta_gpt4_covered": "eloundou_gpt4_covered"})
    out = out.with_columns(z_aioe=_z("E_aioe"), z_eloundou=_z("E_eloundou"),
                           z_eloundou_gpt4=_z("E_eloundou_gpt4"))
    return out.select("ff49", "z_aioe", "z_eloundou", "z_eloundou_gpt4", "E_aioe",
                      "E_eloundou", "E_eloundou_gpt4", "aioe_covered", "eloundou_covered",
                      "eloundou_gpt4_covered", "emp").sort("ff49")


def rank_correlations(bench: pl.DataFrame, exposure: pl.DataFrame) -> pl.DataFrame:
    """Spearman rank correlation across FF49 between benchmark z-scores and the AEI
    `z_delegation` / `z_usage` (descriptive "could vs does"; no test attached)."""
    j = bench.join(exposure.select("ff49", "z_delegation", "z_usage"), on="ff49")
    rows = [{"benchmark": b, "aei": a, "n": j.height,
             "spearman": j.select(pl.corr(b, a, method="spearman")).item()}
            for b in [c for c in bench.columns if c.startswith("z_")]
            for a in ("z_delegation", "z_usage")]
    return pl.DataFrame(rows)


def main() -> int:
    from aideleg.bls.oews import load_national

    national, structure = load_national(2024), _structure()
    raw = load_aioe_raw()
    print(f"AIOE: {raw.height} SOC 2010 codes; coverage of OEWS 2024 employment "
          f"before vintage mapping {coverage(raw, national, structure):.1%}, after "
          f"{coverage(load_aioe(), national, structure):.1%}")
    el = load_eloundou()
    print(f"Eloundou: {el.height} SOC 2018 codes; coverage {coverage(el, national, structure):.1%}")
    occ = benchmark_occupations(national, structure)
    b = benchmark_ff49(occ_values=occ)
    DERIVED.mkdir(parents=True, exist_ok=True)
    b.write_parquet(DERIVED / "benchmark_ff49.parquet")
    print(f"{b.height} FF49 industries; coverage aioe {b['aioe_covered'].min():.3f}-"
          f"{b['aioe_covered'].max():.3f}, eloundou {b['eloundou_covered'].min():.3f}-"
          f"{b['eloundou_covered'].max():.3f}")
    path = DERIVED / "exposure_ff49.parquet"
    if path.exists():
        e = pl.read_parquet(path).filter(pl.col("design") == "B")
        with pl.Config(float_precision=3):
            print("Spearman across FF49 vs AEI Design B (descriptive):",
                  rank_correlations(b, e), sep="\n")
    print("-> data/derived/benchmark_ff49.parquet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
