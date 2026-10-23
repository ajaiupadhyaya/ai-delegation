"""New inputs for the PAP §8.2 robustness rows (Plan 4 Task 6).

AEI data are conversations matched to O*NET tasks; these inputs only re-weight or re-link
them. The study's one disclaimer is `aideleg.results.common.WORDING`.

| function | row | what it replaces |
|---|---|---|
| `wage_bill_matrix` | R2 | `load_industry_matrix(2024, 4)` employment by the wage bill |
| `employment_allocation_table` | R11 | the equal task split of `occupation_table` (D4) |
| `emp_weighted_naics_ff49` | R33 | the equal 6 -> 4-digit split of `naics_to_ff49` (D23) |
| `bls_soc_crosswalk` | R14 | the O*NET-detail union of `map_soc2010_to_2018` (D6) |
| `index_29_2` | R32 | the O*NET 29.3 task statements of `default_index` |
| `consequence_of_error` | R27 | the error-cost indicator of H3 (D15) |
| `public_float` | R29 | the cap proxy for float-weighted filers |

Nothing here writes to `data/derived/`; the bound modules (`aei.tasks`, `bls.oews`,
`occupations`) are read, never edited.
"""

import json
from functools import cache
from pathlib import Path

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW

SOC_RE = r"^\d{2}-\d{4}$"
_SUPPRESSED = ("*", "**", "")


# --- R2: wage-bill weights ----------------------------------------------------------------


def _ind_path(year: int) -> Path:
    from aideleg.bls.oews import _unzipped

    return _unzipped(f"oews_{year}_ind", f"nat4d_M{year}_dl.xlsx")


@cache
def _wage_bill(year: int, path: Path | None) -> pl.DataFrame:
    from aideleg.bls.oews import A_MEDIAN_TOPCODE, _read, load_industry_matrix

    if year not in A_MEDIAN_TOPCODE:
        raise ValueError(f"no OEWS annual top-code recorded for {year} (A_MEDIAN_TOPCODE)")
    topcode = A_MEDIAN_TOPCODE[year]
    path = path or _ind_path(year)
    base = load_industry_matrix(year, 4, path=path)
    raw = _read(path).filter(pl.col("O_GROUP") == "detailed")
    mean = pl.col("A_MEAN")
    a_mean = (
        pl.when(mean == "#")
        .then(pl.lit(topcode))
        .when(mean.is_null() | mean.is_in(_SUPPRESSED))
        .then(pl.lit(None, pl.Float64))
        .otherwise(mean.cast(pl.Float64, strict=True))
    )
    wages = raw.select(naics=pl.col("NAICS"), soc6=pl.col("OCC_CODE"), a_mean=a_mean)
    if wages.select("naics", "soc6").is_duplicated().any():
        raise ValueError(f"{path.name}: more than one detailed row per (NAICS, OCC_CODE)")
    return base.join(wages, on=["naics", "soc6"], how="left").with_columns(
        wage_bill=pl.col("tot_emp").cast(pl.Float64) * pl.col("a_mean")
    )


def wage_bill_matrix(year: int = 2024, *, path: Path | None = None) -> pl.DataFrame:
    """`load_industry_matrix(year, 4)` with `tot_emp` replaced by the wage bill
    `TOT_EMP x A_MEAN` and `emp_share_in_industry` by its within-industry share (R2).

    [default, PAP §11 C-66] An `A_MEAN` of `#` (at or above the annual top-code) is set to
    the May 2024 top-code, $239,200 (PAP §4.1), as for the median; `*` / `**` give a null wage
    bill, which is left out of the shares (like suppressed employment).

    [default, C-66] R2 changes w_oj only: the U_o denominators stay national employment
    shares (`load_national`), so this matrix is used for the industry aggregation alone. In
    `exposure.aggregate_to_ff49` the FF49 weight of an occupation is
    sum_c xw_c * tot_emp_c * share_oc / sum_c xw_c * tot_emp_c over the OEWS codes c of the
    industry, i.e. o's share of FF49 industry j's employment; with this matrix it is o's share
    of j's wage bill. The across-code weight is part of w_oj, so it is replaced too
    (PAP §11 C-72: the wage bill in every industry weight).
    """
    df = _wage_bill(year, path)
    total = pl.col("wage_bill").sum().over("naics")
    return df.select(
        "naics",
        "naics_title",
        "soc6",
        tot_emp="wage_bill",
        emp_share_in_industry=pl.when(total > 0).then(pl.col("wage_bill") / total),
    )


def wage_bill_coverage(year: int = 2024, *, path: Path | None = None) -> float:
    """Share of the matrix's non-suppressed detailed employment that has a wage bill."""
    df = _wage_bill(year, path)
    emp = df.filter(pl.col("tot_emp").is_not_null())
    return float(
        emp.filter(pl.col("wage_bill").is_not_null())["tot_emp"].sum() / emp["tot_emp"].sum()
    )


# --- R11: employment-weighted task allocation ---------------------------------------------


def _study_structure() -> pl.DataFrame:
    return pl.read_csv(RAW / by_key("aei_soc_structure").dest)


_STUDY = object()


def employment_allocation_table(
    panel: pl.DataFrame,
    release: str,
    index,
    national: pl.DataFrame,
    *,
    soc_structure=_STUDY,
) -> pl.DataFrame:
    """`occupation_table(panel, release, index, basis="tasks")` with the task split in
    proportion to employment (R11, the D4 alternative); columns `occupations.COLUMNS`.

    A task's candidate set S is the same union as ruling R6 (every Task ID of its statement
    and its panel `node_id`, truncated to soc6). Each o in S gets
    pct * emp_o / sum_{o' in S} emp_o', with emp_o = `national` `tot_emp` of
    `oews_code_for(o)` divided by the number of members of S sharing that OEWS code (so a
    code's employment is not counted twice). An o with no OEWS code, or a suppressed one, has
    emp_o = 0; if the sum is 0 the task is split equally. Pattern shares are weighted by the
    allocated pct, as in `occupation_table`; `usage_share` is renormalised to 100.

    Task-basis tables only: AEI's published r6 SOC rows (`basis="published"`, D9) have no task
    split to re-weight, so the caller keeps them as published (Plan 4 Task 5 wiring).

    `soc_structure` (default: the AEI SOC structure, as the exposure module uses) enables OEWS
    hybrid codes in `oews_code_for`; `None` disables them.
    """
    from aideleg.bls.oews import oews_code_for
    from aideleg.occupations import _MATCHED, KEY, _aggregate, _task_occupations, _totals, _wide

    if soc_structure is _STUDY:
        soc_structure = _study_structure()
    wide = _wide(panel, release, "onet_task").filter(_MATCHED)
    occ = _task_occupations(wide.select("node_id", "node_name").unique(), index)
    rows = wide.join(occ, on=["node_id", "node_name"], how="left", nulls_equal=True).filter(
        pl.col("soc6").list.len() > 0
    )
    nat = national.filter(pl.col("tot_emp").is_not_null())
    codes = set(nat["soc6"])
    emp_of = dict(zip(nat["soc6"], nat["tot_emp"].cast(pl.Float64), strict=True))
    socs = rows["soc6"].explode().unique().to_list()
    oews = pl.DataFrame(
        {"soc6": socs, "oews": [oews_code_for(s, codes, soc_structure) for s in socs]},
        schema={"soc6": pl.String, "oews": pl.String},
    ).with_columns(
        code_emp=pl.col("oews").replace_strict(emp_of, default=None, return_dtype=pl.Float64)
    )
    task = [*KEY, "node_id"]
    contrib = (
        rows.explode("soc6")
        .join(oews, on="soc6", how="left")
        .with_columns(
            emp_o=(pl.col("code_emp") / pl.len().over(*task, "oews")).fill_null(0.0),
            k=pl.len().over(task),
        )
        .with_columns(tot=pl.col("emp_o").sum().over(task))
        .with_columns(
            w=pl.when(pl.col("tot") > 0)
            .then(pl.col("pct") * pl.col("emp_o") / pl.col("tot"))
            .otherwise(pl.col("pct") / pl.col("k"))
        )
        .drop("oews", "code_emp", "emp_o", "k", "tot")
    )
    return _aggregate(contrib, _totals(rows), "tasks", count_tasks=True, renormalise=True)


# --- R33: employment-weighted NAICS 6 -> 4-digit crosswalk --------------------------------


def _xlsx_strings(path: Path) -> pl.DataFrame:
    import pandas as pd

    df = pd.read_excel(path, dtype=str, engine="openpyxl", keep_default_na=False)
    return pl.from_pandas(df).with_columns(pl.all().str.strip_chars())


@cache
def _published() -> pl.DataFrame:
    """`naics, level, emp`: May 2024 cross-industry totals (`O_GROUP == "total"`, all
    occupations) of the NAICS 5- and 6-digit industries in `nat5d_6d_M2024_dl.xlsx`. A
    5-digit row is printed as its 6-character padded code (`238140` = 23814)."""
    from aideleg.bls.oews import _unzipped

    df = _xlsx_strings(_unzipped("oews_2024_ind", "nat5d_6d_M2024_dl.xlsx"))
    t = df.filter(pl.col("O_GROUP") == "total")
    level = (
        pl.when(pl.col("I_GROUP") == "6-digit")
        .then(6)
        .when(pl.col("I_GROUP") == "5-digit")
        .then(5)
        .cast(pl.Int64)
    )
    out = t.select(
        naics=pl.col("NAICS"), level=level, emp=pl.col("TOT_EMP").cast(pl.Float64, strict=True)
    )
    if out["level"].is_null().any() or out["naics"].is_duplicated().any():
        raise ValueError("nat5d_6d: unexpected I_GROUP or duplicated NAICS among total rows")
    return out


@cache
def _nat4d_totals() -> pl.DataFrame:
    """`naics (4-digit), emp`: the nat4d `total` rows of padded 4-digit codes (`111100`)."""
    from aideleg.bls.oews import _unzipped

    df = _xlsx_strings(_unzipped("oews_2024_ind", "nat4d_M2024_dl.xlsx"))
    t = df.filter((pl.col("O_GROUP") == "total") & pl.col("NAICS").str.contains(r"^\d{4}00$"))
    return t.select(
        naics=pl.col("NAICS").str.slice(0, 4), emp=pl.col("TOT_EMP").cast(pl.Float64, strict=True)
    )


def _child_employment(
    split6: pl.DataFrame, published: pl.DataFrame, totals: pl.DataFrame
) -> pl.DataFrame:
    """`naics (6-digit), n4, e, E`: each 6-digit child's employment weight and its n4 sum."""
    kids = split6.select("naics").unique().with_columns(n4=pl.col("naics").str.slice(0, 4))
    pub6 = {n: e for n, lv, e in published.iter_rows() if lv == 6}
    pub5 = {n[:5]: e for n, lv, e in published.iter_rows() if lv == 5}
    e4 = dict(totals.iter_rows())
    rows = []
    for n4, grp in kids.group_by("n4"):
        n4 = n4[0]
        children = sorted(grp["naics"])
        e: dict[str, float | None] = dict.fromkeys(children)
        for c in children:
            if c in pub6:
                e[c] = pub6[c]
        for p5, v in pub5.items():
            if not p5.startswith(n4):
                continue
            under = [c for c in children if c.startswith(p5)]
            if any(c in pub6 for c in under):
                raise ValueError(f"NAICS {p5} is published with 6-digit children also published")
            for c in under:
                e[c] = v / len(under)
        published_sum = sum(v for v in e.values() if v is not None)
        unpublished = [c for c, v in e.items() if v is None]
        if len(unpublished) == len(children):
            e = dict.fromkeys(children, 1.0)  # no published child: the primary equal split
        elif unpublished:
            if n4 not in e4:
                raise ValueError(f"NAICS {n4} has published children but no nat4d total")
            resid = max(e4[n4] - published_sum, 0.0)
            for c in unpublished:
                e[c] = resid / len(unpublished)
        total = sum(e.values())
        if total <= 0:
            e, total = dict.fromkeys(children, 1.0), float(len(children))
        rows += [(c, n4, e[c], total) for c in children]
    return pl.DataFrame(
        rows,
        orient="row",
        schema={"naics": pl.String, "n4": pl.String, "e": pl.Float64, "E": pl.Float64},
    )


def emp_weighted_naics_ff49(
    siccodes_key: str = "ff_siccodes49",
    *,
    split6: pl.DataFrame | None = None,
    published: pl.DataFrame | None = None,
    totals: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """NAICS 2022 4-digit -> FF49 weighted by May 2024 employment (R33, the D23 variant):
    `naics, ff49, weight`, the shape of `naics_to_ff49("split", 4, "exclude")`.

    weight(n4, f) = sum_c e_c * w6(c, f) / sum_c e_c over the 6-digit NAICS 2022 children c of
    n4 in `naics_ff49._split6(siccodes_key)` (orphan children included, as unmapped). e_c is
    the May 2024 cross-industry `TOT_EMP` of c in `nat5d_6d_M2024_dl.xlsx` (all ownerships,
    `O_GROUP == "total"`). A 5-digit-only published value is split equally over its 6-digit
    children.

    [default, PAP §11 C-67] Children with no published value share the residual
    R = max(E4 - sum published, 0) equally, E4 being n4's `nat4d` total; if no child of n4 is
    published, the primary equal split is used. NAICS 5511 is excluded as in the primary.

    `split6`, `published` (`naics, level, emp`) and `totals` (`naics, emp`) override the study
    inputs (test fixtures).
    """
    from aideleg.crosswalk.naics_ff49 import HQ_NAICS, _split6

    s6 = _split6(siccodes_key) if split6 is None else split6
    pub = _published() if published is None else published
    tot = _nat4d_totals() if totals is None else totals
    e = _child_employment(s6, pub, tot)
    return (
        s6.join(e, on="naics")
        .group_by(naics="n4", ff49="ff49")
        .agg(weight=(pl.col("weight") * pl.col("e") / pl.col("E")).sum())
        .filter(~pl.col("naics").str.starts_with(HQ_NAICS))
        .select("naics", "ff49", "weight")
        .sort("naics", "ff49", nulls_last=True)
    )


# --- R14: BLS SOC 2010 -> 2018 crosswalk --------------------------------------------------


ONET_FALLBACK = frozenset({"19-1020"})  # C-73: the only non-SOC-2010 code AIOE carries


@cache
def bls_soc_crosswalk() -> pl.DataFrame:
    """`o2010, o2019`: the BLS SOC 2010 -> 2018 crosswalk (`bls_soc_2010_2018`), 7-character
    codes, the shape `benchmarks.map_soc2010_to_2018` takes (R14, the D6 alternative).

    [default, PAP §11 C-73] A 2010 code the BLS file does not list is not a SOC 2010
    detailed code but an O*NET-SOC one (AIOE's `19-1020`, from O*NET-SOC `19-1020.01`
    Biologists). Such a code takes its O*NET 2010 -> 2019 successors, so that AIOE can be
    mapped in full; every SOC 2010 code keeps the BLS mapping. The fallback codes must be
    exactly `ONET_FALLBACK` (ValueError otherwise), so its scope cannot widen silently.
    """
    import pandas as pd

    path = RAW / by_key("bls_soc_2010_2018").dest
    raw = pd.read_excel(path, header=None, dtype=str).fillna("")
    hit = [i for i in range(min(len(raw), 20)) if raw.iat[i, 0].strip() == "2010 SOC Code"]
    if not hit or raw.iat[hit[0], 2].strip() != "2018 SOC Code":
        raise ValueError(f"{path.name}: no '2010 SOC Code' / '2018 SOC Code' header row")
    body = raw.iloc[hit[0] + 1 :]
    bls = pl.DataFrame(
        {
            "o2010": body.iloc[:, 0].str.strip().tolist(),
            "o2019": body.iloc[:, 2].str.strip().tolist(),
        }
    )
    bls = bls.filter(pl.col("o2010").str.contains(SOC_RE) & pl.col("o2019").str.contains(SOC_RE))
    onet = pl.read_csv(
        RAW / by_key("onet_2010_2019_crosswalk").dest,
        columns=["O*NET-SOC 2010 Code", "O*NET-SOC 2019 Code"],
    )
    onet = onet.select(
        o2010=pl.col("O*NET-SOC 2010 Code").str.slice(0, 7),
        o2019=pl.col("O*NET-SOC 2019 Code").str.slice(0, 7),
    )
    extra = onet.filter(~pl.col("o2010").is_in(bls["o2010"].implode()))
    if set(extra["o2010"]) != ONET_FALLBACK:
        raise ValueError(
            f"O*NET fallback codes {sorted(set(extra['o2010']))} != {sorted(ONET_FALLBACK)} (C-73)"
        )
    return pl.concat([bls, extra]).unique().sort("o2010", "o2019")


# --- R32: O*NET 29.2 task index -----------------------------------------------------------


@cache
def index_29_2():
    """`TaskIndex.build(onet_29_2_tasks, aei_onet_tasks, onet_2010_2019_crosswalk)` (R32: task
    statements public at the formation date, O*NET 29.2, February 2025).

    The downloaded 29.2 `Task Statements.txt` is byte-identical to the 29.3 file (SHA-256
    fecdcda8...; latest task `Date` 08/2024), so this index equals `default_index()` and R32's
    O*NET part is identical to the primary (PAP §11 C-74).
    """
    from aideleg.aei.tasks import TaskIndex

    return TaskIndex.build(
        RAW / by_key("onet_29_2_tasks").dest,
        RAW / by_key("aei_onet_tasks").dest,
        RAW / by_key("onet_2010_2019_crosswalk").dest,
    )


# --- R27, R29 -----------------------------------------------------------------------------


def consequence_of_error(path: Path | None = None) -> pl.DataFrame:
    """`soc6, coe`: the simple mean of `Data Value` over the O*NET-SOC codes within soc6 for
    `Element Name == "Consequence of Error"`, `Scale ID == "CX"` (O*NET 29.3 Work Context;
    R27, PAP §11 C-58 for its standardisation, done by the caller)."""
    path = path or RAW / by_key("onet_29_3_work_context").dest
    df = pl.read_csv(path, separator="\t", quote_char=None, infer_schema_length=0)
    sub = df.filter(
        (pl.col("Element Name") == "Consequence of Error") & (pl.col("Scale ID") == "CX")
    )
    return (
        sub.select(
            soc6=pl.col("O*NET-SOC Code").str.slice(0, 7),
            v=pl.col("Data Value").cast(pl.Float64, strict=True),
        )
        .group_by("soc6")
        .agg(coe=pl.col("v").mean())
        .sort("soc6")
    )


def public_float(path: Path | None = None) -> pl.DataFrame:
    """`cik, public_float_usd`: the SEC XBRL frame `dei/EntityPublicFloat/USD/CY2024Q2I`
    (R29's cap proxy, PAP §11 C-61). Raises on a repeated CIK."""
    path = path or RAW / by_key("sec_public_float_cy2024q2").dest
    data = json.loads(Path(path).read_text())["data"]
    out = pl.DataFrame(
        {"cik": [d["cik"] for d in data], "public_float_usd": [d["val"] for d in data]},
        schema={"cik": pl.Int64, "public_float_usd": pl.Float64},
    )
    if out["cik"].is_duplicated().any():
        raise ValueError("public float frame has a CIK more than once")
    return out.sort("cik")
