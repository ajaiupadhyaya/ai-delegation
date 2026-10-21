"""NAICS 2022 -> SIC 1987 -> Fama-French 49 industries, and its coverage of OEWS employment.

Chain. The Census concordances link SIC 1987 -> NAICS 1997 -> 2002 -> 2007 -> 2012 -> 2017
-> 2022. Each link is many-to-many. A source code's weight is split equally over its
distinct targets, unless the link carries an explicit `share` column (none of the six Census
files does). Composing the links gives `w(sic, naics22)`; inverting by normalising over SIC
gives `w(naics22 -> sic)`, which sums to 1 for every NAICS 2022 code.

Layouts (inspected 2026-10-21; header rows differ, so codes are found by pattern, not position):
- `1987_SIC_to_1997_NAICS.xls`: header on row 0 (`SIC`, `Part Indicator`, ..., `1997 NAICS`).
  Columns 0 (SIC) and 3 (NAICS 1997). 2-digit SIC rows are group headings; a 4-digit SIC with
  a blank NAICS is the parent of the `pt` rows below it. NAICS 1997 is printed with 5 digits
  where the 6-digit U.S. code just appends a `0` (e.g. `51121` = 511210), so it is padded. Four
  rows point to a whole sector or subsector (`23`, `315`, `522`, `532`, "Included in ..."):
  they expand to every NAICS 1997 code with that prefix.
- `1997_NAICS_to_2002_NAICS.xls`: sheet `Concordance 23 US NoD` (sheet `Sheet1` is a pivot
  count), header on row 0 (`NAICS97`, ..., `NAICS02`). Columns 0 and 2.
- `2002_to_2007_NAICS.xls`, `2007_to_2012_NAICS.xls`, `2012_to_2017_NAICS.xlsx`,
  `2017_to_2022_NAICS.xlsx`: two title/note rows, header on row 2 (`20xx NAICS Code`, title,
  `20yy NAICS Code`, title, then empty columns). Columns 0 and 2.

FF49. A SIC maps to an industry only if it lies inside one of the ranges listed in
`Siccodes49.txt`. In that file industry 49 is `Other` ("Almost Nothing": SIC 4950-4959,
4960-4961, 4970-4971, 4990-4991); 48 is `Fin` ("Trading"). A SIC outside every listed range,
`Other`'s included, is unmapped: it is never pushed into `Other`. (The task brief called
Other "#48"; the file numbers it 49, and #48 is `Fin`.)

OEWS. The 4-digit OEWS file pads codes to six characters (`511200`) and publishes some BLS
aggregates with letters (`3250A1`). Padded codes map by their first 4 digits. A letter
aggregate is the equal-weight union of the 4-digit industries its title lists, e.g. "Chemical
Manufacturing (3251, 3252, 3253, and 3259 only)". The component list is in the title, not in
`file_descriptions.xlsx` (that file only lists the workbooks). NAICS `99xxxx` (OEWS federal,
state and local government designations) and the explicit list `NO_PUBLIC_EQUITY` (`491100`
Postal Service, Federal Government) form the "government: no public equity" bucket, outside
both "mapped" and "unmapped" and outside the private-employment denominator. NAICS 5511
(Management of Companies) is a separate bucket by default; see `naics_to_ff49`.

The nat4d codes are mutually exclusive: no letter aggregate co-exists with its own
components and no 3-digit code with its 4-digit children (checked in `_oews_ff49`).
"""

import re
from collections.abc import Callable, Sequence
from functools import cache
from pathlib import Path
from typing import Literal

import pandas as pd
import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW

VINTAGES = (1997, 2002, 2007, 2012, 2017, 2022)
_LINKS = {  # target vintage -> (source key, sheet)
    1997: ("census_sic87_naics97", 0),
    2002: ("census_naics97_02", "Concordance 23 US NoD"),
    2007: ("census_naics02_07", 0),
    2012: ("census_naics07_12", 0),
    2017: ("census_naics12_17", 0),
    2022: ("census_naics17_22", 0),
}
_HEADER = {  # target vintage -> header text expected in (src col, dst col)
    1997: ("SIC", "1997 NAICS"),
    2002: ("NAICS97", "NAICS02"),
    2007: ("2002 NAICS Code", "2007 NAICS Code"),
    2012: ("2007 NAICS Code", "2012 NAICS Code"),
    2017: ("2012 NAICS Code", "2017 NAICS Code"),
    2022: ("2017 NAICS Code", "2022 NAICS Code"),
}
_LINK_SCHEMA = {"src": pl.String, "dst": pl.String}


def _cells(path: Path, sheet: int | str) -> pd.DataFrame:
    engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
    df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=str, engine=engine)
    return df.fillna("").apply(lambda c: c.str.strip())


def _check_header(df: pd.DataFrame, src_col: int, dst_col: int, want: tuple[str, str],
                  path: Path) -> None:
    for i in range(min(len(df), 6)):
        if df.iat[i, src_col].startswith(want[0]) and df.iat[i, dst_col].startswith(want[1]):
            return
    raise ValueError(f"{path.name}: no header row with {want!r} in columns {src_col},{dst_col}")


@cache
def _link(target: int, raw: Path = RAW) -> pl.DataFrame:
    """One concordance as distinct `(src, dst)` pairs of codes."""
    key, sheet = _LINKS[target]
    path = raw / by_key(key).dest
    df = _cells(path, sheet)
    src_col, dst_col = (0, 3) if target == 1997 else (0, 2)
    _check_header(df, src_col, dst_col, _HEADER[target], path)
    src, dst = df.iloc[:, src_col], df.iloc[:, dst_col]
    if target == 1997:
        keep = src.str.fullmatch(r"\d{4}") & dst.str.fullmatch(r"\d{2,6}")
        pairs = pl.DataFrame({"src": src[keep].tolist(), "dst": dst[keep].tolist()})
        universe = sorted(_link(2002, raw)["src"].unique())
        pairs = pairs.with_columns(
            dst=pl.when(pl.col("dst").str.len_chars() == 5).then(pl.col("dst") + "0")
            .otherwise(pl.col("dst"))
        )
        short = pairs.filter(pl.col("dst").str.len_chars() < 5)
        expanded = [(s, u) for s, d in short.iter_rows() for u in universe if u.startswith(d)]
        pairs = pl.concat([
            pairs.filter(pl.col("dst").str.len_chars() == 6),
            pl.DataFrame(expanded, schema=_LINK_SCHEMA, orient="row"),
        ])
    else:
        keep = src.str.fullmatch(r"\d{6}") & dst.str.fullmatch(r"\d{6}")
        pairs = pl.DataFrame({"src": src[keep].tolist(), "dst": dst[keep].tolist()})
    if pairs.is_empty():
        raise ValueError(f"{path.name}: no code pairs found")
    return pairs.unique().sort("src", "dst")


def _weighted(link: pl.DataFrame) -> pl.DataFrame:
    if "share" in link.columns:
        return link.select("src", "dst", weight=pl.col("share").cast(pl.Float64))
    link = link.select("src", "dst").unique()
    return link.with_columns(weight=1.0 / pl.len().over("src"))


def chain_links(links: Sequence[pl.DataFrame]) -> pl.DataFrame:
    """Compose concordance links into `src, dst, weight` from the first source vintage to the
    last target vintage. Within a link a source's weight is split equally over its distinct
    targets, or taken from a `share` column when the link has one. Codes that do not
    continue into the next link drop out."""
    out = _weighted(links[0])
    for link in links[1:]:
        nxt = _weighted(link).rename({"src": "dst", "dst": "_next", "weight": "_w"})
        out = (out.join(nxt, on="dst", how="inner")
               .group_by("src", "_next").agg(weight=(pl.col("weight") * pl.col("_w")).sum())
               .rename({"_next": "dst"}))
    return out.select("src", "dst", "weight").sort("src", "dst")


def invert(chained: pl.DataFrame) -> pl.DataFrame:
    """`src (SIC), dst (NAICS), weight` -> `naics, sic, weight`, weights summing to 1 per
    NAICS code."""
    return (chained.with_columns(weight=pl.col("weight") / pl.col("weight").sum().over("dst"))
            .select(naics=pl.col("dst"), sic=pl.col("src").cast(pl.Int64), weight="weight")
            .sort("naics", "sic"))


@cache
def naics_to_sic(naics_vintage: int = 2022) -> pl.DataFrame:
    """NAICS (6-digit, the given vintage) -> SIC 1987: `naics, sic, weight`; weights sum to 1
    per NAICS code."""
    if naics_vintage not in VINTAGES:
        raise ValueError(f"naics_vintage must be one of {VINTAGES}, not {naics_vintage!r}")
    links = [_link(v) for v in VINTAGES if v <= naics_vintage]
    return invert(chain_links(links))


def sic_to_ff49(siccodes: pl.DataFrame) -> Callable[[int], int | None]:
    """A lookup SIC -> FF49 industry number, or None for a SIC outside every listed range.
    Ranges are inclusive; where two ranges overlap the first listed wins."""
    ranges = list(siccodes.select("sic_lo", "sic_hi", "ff49").iter_rows())

    def lookup(sic: int) -> int | None:
        for lo, hi, ff in ranges:
            if lo <= sic <= hi:
                return ff
        return None

    return lookup


def _siccodes() -> pl.DataFrame:
    from aideleg.market.french import _single_file, read_siccodes

    return read_siccodes(_single_file("ff_siccodes49"))


HQ_NAICS = "5511"  # Management of Companies and Enterprises
NO_PUBLIC_EQUITY = frozenset({"491100"})  # OEWS codes outside 99xxxx with no listed equity
Status = Literal["private", "government", "management_of_companies"]


@cache
def _split6() -> pl.DataFrame:
    """6-digit NAICS 2022 -> FF49 split, every NAICS 2022 code in the 2017->2022 target list
    included: a code the chain never reaches (no SIC 1987 source: 112130, 481219, 541120,
    551114) gets one null-`ff49` row at weight 1, i.e. it is wholly unmapped."""
    lookup = sic_to_ff49(_siccodes())
    xw = naics_to_sic(2022).with_columns(
        ff49=pl.col("sic").map_elements(lookup, return_dtype=pl.Int64)
    )
    out = xw.group_by("naics", "ff49").agg(pl.col("weight").sum())
    every = _link(2022).select(naics="dst").unique()
    orphan = every.join(out, on="naics", how="anti").with_columns(
        ff49=pl.lit(None, pl.Int64), weight=pl.lit(1.0))
    return pl.concat([out, orphan.select(out.columns)]).sort("naics", "ff49", nulls_last=True)


def _to_digits(df6: pl.DataFrame, digits: int) -> pl.DataFrame:
    if digits == 6:
        return df6
    if digits != 4:
        raise ValueError(f"digits must be 4 or 6, not {digits!r}")
    n6 = df6.select("naics").unique().with_columns(n4=pl.col("naics").str.slice(0, 4))
    n6 = n6.with_columns(k=pl.len().over("n4"))
    return (df6.join(n6, on="naics")
            .group_by(naics="n4", ff49="ff49")
            .agg(weight=(pl.col("weight") / pl.col("k")).sum()))


@cache
def _excluded(method: str, digits: int) -> pl.DataFrame:
    out = _to_digits(_split6(), digits).filter(~pl.col("naics").str.starts_with(HQ_NAICS))
    if method == "majority":
        out = majority(out)
    return out.select("naics", "ff49", "weight").sort("naics", "ff49", nulls_last=True)


@cache
def _default_employment() -> pl.DataFrame:
    from aideleg.bls.oews import load_industry_matrix

    return load_industry_matrix(2024, 4)


def hq_shares(employment: pl.DataFrame, method: Literal["split", "majority"] = "split"
              ) -> pl.DataFrame:
    """`ff49, weight`: each FF49 industry's share of mapped private employment (OEWS codes
    outside government, `NO_PUBLIC_EQUITY` and 5511), under the 5511-excluded crosswalk."""
    by = _oews_ff49(employment, _excluded(method, 4), "exclude")
    emp = (by.filter((pl.col("status") == "private") & pl.col("ff49").is_not_null())
           .group_by("ff49").agg(e=pl.col("emp").sum()))
    return emp.select("ff49", weight=pl.col("e") / pl.col("e").sum()).sort("ff49")


def naics_to_ff49(method: Literal["split", "majority"] = "split",
                  digits: Literal[4, 6] = 4,
                  hq: Literal["exclude", "redistribute"] = "exclude", *,
                  employment: pl.DataFrame | None = None) -> pl.DataFrame:
    """NAICS 2022 -> FF49: `naics, ff49, weight`. `ff49` is null for the weight that reaches
    no FF49 industry, so weights sum to 1 per NAICS code.

    `digits=4` gives each 4-digit industry the equal-weight mean of all its 6-digit codes
    (source-less ones included, as unmapped). `"majority"`: see `majority`.

    NAICS 5511 (Management of Companies: head offices, mostly of non-financial firms) maps
    through SIC 6712/6719 to `Fin` by the concordance, which would put about 2.8M HQ jobs in
    Trading. `hq="exclude"` (default) leaves 5511 out of this table altogether: it is its own
    `management_of_companies` bucket, neither FF49 nor unmapped. `hq="redistribute"` (a
    robustness check, the SIC 1987 treatment of auxiliary establishments) gives every 5511
    code the FF49 mix of mapped private employment, `hq_shares(employment, method)`.
    `employment` is an industry-occupation matrix like `load_industry_matrix`'s output; when
    omitted it is `load_industry_matrix(2024, 4)` (May 2024 OEWS). Under `"majority"` the
    5511 rows stay proportional: the redistribution is not a concordance share to round.

    Equal-split artifacts. Weights are structural, not employment-based: the inversion gives
    each SIC equal mass, so a SIC that maps to a single NAICS outweighs one spread over
    several. E.g. 488111 (Air Traffic Control) is 2/3 SIC 9621 (government regulation of
    transportation, unmapped) and 1/3 SIC 4581 (airports, `Trans`), because 4581 is split
    over three NAICS codes and 9621 is not.
    """
    if method not in ("split", "majority"):
        raise ValueError(f"method must be 'split' or 'majority', not {method!r}")
    if hq not in ("exclude", "redistribute"):
        raise ValueError(f"hq must be 'exclude' or 'redistribute', not {hq!r}")
    out = _excluded(method, digits)
    if hq == "redistribute":
        shares = hq_shares(employment if employment is not None else _default_employment(),
                           method)
        codes = (_to_digits(_split6(), digits).select("naics").unique()
                 .filter(pl.col("naics").str.starts_with(HQ_NAICS)))
        out = pl.concat([out, codes.join(shares, how="cross").select(out.columns)])
    return out.sort("naics", "ff49", nulls_last=True)


def majority(split: pl.DataFrame) -> pl.DataFrame:
    """Assign each NAICS code wholly (weight 1) to its largest-weight FF49 industry. The
    unmapped share (null `ff49`) competes too: a code whose largest share reaches no FF49
    industry stays unmapped. Ties go to a mapped industry, then to the lowest industry
    number. The literal reading ("largest FF49 industry", unmapped not competing) would
    instead send 4911 Postal Service (97% SIC 4311, unmapped) wholly to `BusSv` on its 3% SIC
    7389 slice, and would leave no private employment unmapped under majority."""
    best = (split.sort(["naics", "weight", "ff49"], descending=[False, True, False],
                       nulls_last=True)
            .group_by("naics", maintain_order=True).first()
            .with_columns(weight=pl.lit(1.0)))
    return best.select("naics", "ff49", "weight").sort("naics")


_COMPONENT_RE = re.compile(r"\(([^()]*\bonly)\)")


def oews_components(code: str, title: str) -> list[str] | None:
    """The NAICS industries (4-digit, or 3-digit for a `xxx000` code) an OEWS 4-digit-file
    code stands for; None for the government designations (`99xxxx`)."""
    if code.startswith("99"):
        return None
    if code.isdigit():
        # NAICS pads with zeros: no 2022 4-digit industry ends in 0 (`_weights_for` checks
        # this against the crosswalk), so `455000` is the 3-digit industry 455 and `511200`
        # the 4-digit 5112.
        return [code[:3]] if code[3] == "0" else [code[:4]]
    m = _COMPONENT_RE.search(title)
    parts = re.findall(r"\b\d{4}\b", m.group(1)) if m else []
    if not parts:
        raise ValueError(f"OEWS aggregate {code!r} lists no components in title {title!r}")
    return parts


def oews_status(code: str, hq: Literal["exclude", "redistribute"] = "exclude") -> Status:
    """`government` for 99xxxx and `NO_PUBLIC_EQUITY` (no listed equity: excluded from FF49
    indices and from the private denominator); `management_of_companies` for 5511 when it
    is excluded; otherwise `private`."""
    if code.startswith("99") or code in NO_PUBLIC_EQUITY:
        return "government"
    if hq == "exclude" and code.startswith(HQ_NAICS):
        return "management_of_companies"
    return "private"


def _weights_for(comps: list[str], table: dict[str, list[tuple[int | None, float]]]
                 ) -> dict[int | None, float]:
    """FF49 weights of an OEWS code: the equal-weight mean over its components; a 3-digit
    component is the equal-weight mean over the 4-digit crosswalk codes it prefixes; a
    component the crosswalk lacks is wholly unmapped."""
    out: dict[int | None, float] = {}
    for comp in comps:
        if len(comp) == 3:
            if comp + "0" in table:
                raise ValueError(f"crosswalk has 4-digit code {comp}0: the xxx000 rule fails")
            kids = [k for k in table if k.startswith(comp)]
        else:
            kids = [comp] if comp in table else []
        rows = [r for k in kids for r in table[k]] if kids else [(None, 1.0)]
        n = len(kids) or 1
        for ff, w in rows:
            out[ff] = out.get(ff, 0.0) + w / n / len(comps)
    return out


def _leaves(comps: list[str], keys: set[str]) -> set[str]:
    return {k for c in comps for k in keys if k.startswith(c)} or set(comps)


def _oews_ff49(matrix: pl.DataFrame, xw: pl.DataFrame,
               hq: Literal["exclude", "redistribute"]) -> pl.DataFrame:
    """Long form: `naics, naics_title, status, tot_emp, ff49, emp` (`emp` = the code's
    employment times its FF49 weight; one null-`ff49` row for non-private codes)."""
    if not xw.is_empty() and set(xw["naics"].str.len_chars().unique()) != {4}:
        raise ValueError("the OEWS crosswalk must be keyed by 4-digit NAICS")
    table: dict[str, list[tuple[int | None, float]]] = {}
    for n, ff, w in xw.select("naics", "ff49", "weight").iter_rows():
        table.setdefault(n, []).append((ff, w))
    keys = set(table)
    ind = (matrix.group_by("naics", "naics_title")
           .agg(tot_emp=pl.col("tot_emp").sum().cast(pl.Float64)).sort("naics"))
    rows, seen = [], {}
    for code, title, emp in ind.iter_rows():
        status = oews_status(code, hq)
        if status != "private":
            rows.append((code, title, status, emp, None, 0.0))
            continue
        comps = oews_components(code, title)
        assert comps is not None
        for leaf in _leaves(comps, keys):  # nat4d codes must not overlap
            if leaf in seen:
                raise ValueError(f"OEWS codes {seen[leaf]} and {code} both cover NAICS {leaf}")
            seen[leaf] = code
        for ff, w in _weights_for(comps, table).items():
            rows.append((code, title, status, emp, ff, emp * w))
    return pl.DataFrame(rows, orient="row", schema={
        "naics": pl.String, "naics_title": pl.String, "status": pl.String,
        "tot_emp": pl.Float64, "ff49": pl.Int64, "emp": pl.Float64})


def coverage_by_code(matrix: pl.DataFrame, method: Literal["split", "majority"] = "split",
                     hq: Literal["exclude", "redistribute"] = "exclude", *,
                     crosswalk: pl.DataFrame | None = None,
                     employment: pl.DataFrame | None = None) -> pl.DataFrame:
    """Per OEWS industry: `naics, naics_title, status, tot_emp, mapped_emp, unmapped_emp`.
    `status` is `private`, `government` (99xxxx and `NO_PUBLIC_EQUITY`) or
    `management_of_companies` (5511, when `hq="exclude"`); only private codes have mapped or
    unmapped employment. `tot_emp` sums the non-suppressed detailed employment. Values are
    rounded to 6 decimals (float residuals of ~1e-10 become 0). Raises if two OEWS codes
    cover the same 4-digit NAICS (nothing is counted twice)."""
    if crosswalk is None:
        crosswalk = naics_to_ff49(method, 4, hq, employment=employment)
    long = _oews_ff49(matrix, crosswalk, hq)
    priv = pl.col("status") == "private"
    return (long.group_by("naics", "naics_title", "status", "tot_emp", maintain_order=True)
            .agg(mapped_emp=pl.col("emp").filter(priv & pl.col("ff49").is_not_null()).sum(),
                 unmapped_emp=pl.col("emp").filter(priv & pl.col("ff49").is_null()).sum())
            .with_columns(pl.col("mapped_emp", "unmapped_emp").round(6))
            .sort("naics"))


def coverage_report(matrix: pl.DataFrame, method: Literal["split", "majority"] = "split",
                    hq: Literal["exclude", "redistribute"] = "exclude", *,
                    crosswalk: pl.DataFrame | None = None,
                    employment: pl.DataFrame | None = None) -> pl.DataFrame:
    """Employment by mapping status: `status (mapped | unmapped | management_of_companies |
    government), tot_emp, share_of_total, share_of_private`. The private denominator is
    mapped + unmapped; `share_of_private` is null for the two excluded buckets. With
    `hq="redistribute"` 5511 is mapped and its bucket is 0."""
    by = coverage_by_code(matrix, method, hq, crosswalk=crosswalk, employment=employment)

    def bucket(s: str) -> float:
        return by.filter(pl.col("status") == s)["tot_emp"].sum()

    mapped, unmapped = by["mapped_emp"].sum(), by["unmapped_emp"].sum()
    hq_emp, gov = bucket("management_of_companies"), bucket("government")
    total, private = mapped + unmapped + hq_emp + gov, mapped + unmapped
    rows = [("mapped", mapped, mapped / total, mapped / private),
            ("unmapped", unmapped, unmapped / total, unmapped / private),
            ("management_of_companies", hq_emp, hq_emp / total, None),
            ("government", gov, gov / total, None)]
    return pl.DataFrame(rows, orient="row", schema={
        "status": pl.String, "tot_emp": pl.Float64, "share_of_total": pl.Float64,
        "share_of_private": pl.Float64})
