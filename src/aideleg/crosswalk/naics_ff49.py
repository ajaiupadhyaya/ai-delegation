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
`Other`'s included, is unmapped: it is never pushed into `Other`.

OEWS. The 4-digit OEWS file pads codes to six characters (`511200`) and publishes some BLS
aggregates with letters (`3250A1`). Padded codes map by their first 4 digits. A letter
aggregate is the equal-weight union of the 4-digit industries its title lists, e.g. "Chemical
Manufacturing (3251, 3252, 3253, and 3259 only)". The component list is in the title, not in
`file_descriptions.xlsx` (that file only lists the workbooks). NAICS `99xxxx` (OEWS federal,
state and local government designations) is the "government: no public equity" bucket,
outside both "mapped" and "unmapped" and outside the private-employment denominator.
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


@cache
def naics_to_ff49(method: Literal["split", "majority"] = "split",
                  digits: Literal[4, 6] = 4) -> pl.DataFrame:
    """NAICS 2022 -> FF49: `naics, ff49, weight`. `ff49` is null for the weight that reaches
    no FF49 industry, so weights sum to 1 per NAICS code.

    `digits=4` gives each 4-digit industry the equal-weight mean of its 6-digit codes.
    `"majority"`: see `majority`.
    """
    if method not in ("split", "majority"):
        raise ValueError(f"method must be 'split' or 'majority', not {method!r}")
    lookup = sic_to_ff49(_siccodes())
    xw = naics_to_sic(2022).with_columns(
        ff49=pl.col("sic").map_elements(lookup, return_dtype=pl.Int64)
    )
    out = xw.group_by("naics", "ff49").agg(pl.col("weight").sum())
    if digits == 4:
        n6 = out.select("naics").unique().with_columns(n4=pl.col("naics").str.slice(0, 4))
        n6 = n6.with_columns(k=pl.len().over("n4"))
        out = (out.join(n6, on="naics")
               .group_by(naics="n4", ff49="ff49")
               .agg(weight=(pl.col("weight") / pl.col("k")).sum()))
    elif digits != 6:
        raise ValueError(f"digits must be 4 or 6, not {digits!r}")
    if method == "majority":
        out = majority(out)
    return out.select("naics", "ff49", "weight").sort("naics", "ff49", nulls_last=True)


def majority(split: pl.DataFrame) -> pl.DataFrame:
    """Assign each NAICS code wholly (weight 1) to its largest-weight FF49 industry. The
    unmapped share (null `ff49`) competes too: a code whose largest share reaches no FF49
    industry stays unmapped rather than going to a minor FF49 slice (Postal Service, 97%
    SIC 4311, is not made Business Services by its 3% SIC 7389). Ties go to a mapped
    industry, then to the lowest industry number."""
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
        # NAICS pads with zeros: no 2022 4-digit industry ends in 0, so `455000` is the
        # 3-digit industry 455 and `511200` the 4-digit 5112.
        return [code[:3]] if code[3] == "0" else [code[:4]]
    m = _COMPONENT_RE.search(title)
    parts = re.findall(r"\b\d{4}\b", m.group(1)) if m else []
    if not parts:
        raise ValueError(f"OEWS aggregate {code!r} lists no components in title {title!r}")
    return parts


def _prefix_frac(frac: dict[str, float], comp: str) -> float:
    """Mapped fraction of a component: its own entry, or the equal-weight mean over the
    crosswalk codes it prefixes (a 3-digit component); 0 when the crosswalk has none."""
    if comp in frac:
        return frac[comp]
    hits = [v for k, v in frac.items() if k.startswith(comp)]
    return sum(hits) / len(hits) if hits else 0.0


def coverage_by_code(matrix: pl.DataFrame, method: Literal["split", "majority"] = "split", *,
                     crosswalk: pl.DataFrame | None = None) -> pl.DataFrame:
    """Per OEWS industry: `naics, naics_title, status ("government" | "private"), tot_emp,
    mapped_emp, unmapped_emp`. `tot_emp` sums the non-suppressed detailed employment. A
    letter aggregate's mapped fraction is the mean over its components; a component missing
    from the crosswalk counts as unmapped."""
    xw = crosswalk if crosswalk is not None else naics_to_ff49(method)
    frac = dict(xw.group_by("naics")
                .agg(pl.col("weight").filter(pl.col("ff49").is_not_null()).sum())
                .iter_rows())
    ind = (matrix.group_by("naics", "naics_title")
           .agg(tot_emp=pl.col("tot_emp").sum().cast(pl.Float64)).sort("naics"))
    rows = []
    for code, title, emp in ind.iter_rows():
        comps = oews_components(code, title)
        if comps is None:
            rows.append((code, title, "government", emp, 0.0, 0.0))
            continue
        f = sum(_prefix_frac(frac, c) for c in comps) / len(comps)
        rows.append((code, title, "private", emp, emp * f, emp * (1 - f)))
    return pl.DataFrame(rows, orient="row", schema={
        "naics": pl.String, "naics_title": pl.String, "status": pl.String,
        "tot_emp": pl.Float64, "mapped_emp": pl.Float64, "unmapped_emp": pl.Float64})


def coverage_report(matrix: pl.DataFrame, method: Literal["split", "majority"] = "split", *,
                    crosswalk: pl.DataFrame | None = None) -> pl.DataFrame:
    """Employment by mapping status: `status (mapped | unmapped | government), tot_emp,
    share_of_total, share_of_private`. `share_of_private` is null for government."""
    by = coverage_by_code(matrix, method, crosswalk=crosswalk)
    gov = by.filter(pl.col("status") == "government")["tot_emp"].sum()
    mapped, unmapped = by["mapped_emp"].sum(), by["unmapped_emp"].sum()
    total, private = mapped + unmapped + gov, mapped + unmapped
    rows = [("mapped", mapped, mapped / total, mapped / private),
            ("unmapped", unmapped, unmapped / total, unmapped / private),
            ("government", gov, gov / total, None)]
    return pl.DataFrame(rows, orient="row", schema={
        "status": pl.String, "tot_emp": pl.Float64, "share_of_total": pl.Float64,
        "share_of_private": pl.Float64})
