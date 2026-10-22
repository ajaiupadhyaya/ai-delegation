"""RQ1 geography: the descriptive H4 shift-share split and the choropleth specs.

AEI data are conversations matched to O*NET tasks. A row is one geography's conversations in r6
(`claude_ai`). Nothing here is a test: no p-value, no estimator. The split is the identity
gap = mix_part + within_part, with gap = automation_pct - global_automation,
mix_part = mix - global_automation and within_part = automation_pct - mix. Because `m_global`
(the mix formula applied to the global shares) is not `global_automation`, every `mix_part`
carries the common offset `m_global - global_automation`.

AUI (Anthropic Usage Index): a geography's share of Claude usage divided by its share of
working-age population.
"""

from dataclasses import dataclass
from typing import Literal

import polars as pl

from aideleg.acquire.sources import by_key
from aideleg.config import RAW
from aideleg.figures import DIVERGING_CMAP, SEQUENTIAL_CMAP
from aideleg.rq1 import h4

Geo = Literal["country", "us_state"]
TABLE_COLUMNS = ["geo_id", "name", "automation_pct", "aui", "mix", "gap", "mix_part",
                 "within_part", "in_h4_sample"]
# Natural Earth codes Kosovo KOS; AEI, the GDP and population files code it XKX.
NE_ALIAS = {"XKX": "KOS"}


# AUI is shown diverging, centred at parity (log10 AUI = 0): a presentation choice.
AUI_TICKS = (0.1, 0.25, 0.5, 0.7, 1.0, 1.4, 2.0, 4.0)
AUI_TICKLABELS = ("0.1", "0.25", "0.5", "0.7", "1", "1.4", "2", "4")
AUI_LABEL = "AUI (log scale; 1 = share of usage equals share of working-age population)"
CLIP = (2.0, 98.0)  # percentiles at which the diverging colour scales are cut


@dataclass(frozen=True)
class MapSpec:
    column: str  # column of the geography table
    cmap: str
    center: float | None  # diverging maps are centred here
    log: bool  # colour on a log10 scale
    fig_name: str
    label: str
    title: str


def _specs(prefix: str, where: str) -> tuple[MapSpec, ...]:
    return (
        MapSpec("automation_pct", SEQUENTIAL_CMAP, None, False, f"fig_rq1_map_{prefix}_automation",
                "automation pattern share (% of classified conversations)",
                f"Automation-pattern share of conversations, {where}"),
        MapSpec("aui", DIVERGING_CMAP, 0.0, True, f"fig_rq1_map_{prefix}_aui",
                AUI_LABEL,
                f"Anthropic Usage Index, {where}"),
        MapSpec("mix_part", DIVERGING_CMAP, 0.0, False, f"fig_rq1_map_{prefix}_mix",
                "mix part of the gap (pp; includes the common offset)",
                f"Mix part of the gap from the global automation share, {where}"),
        MapSpec("within_part", DIVERGING_CMAP, 0.0, False, f"fig_rq1_map_{prefix}_within",
                "within part of the gap (pp)",
                f"Within part of the gap from the global automation share, {where}"),
    )


MAPS: dict[str, tuple[MapSpec, ...]] = {
    "country": _specs("country", "countries"),
    "us_state": _specs("state", "US states"),
}


def _names(geo: Geo, names: pl.DataFrame | None) -> pl.DataFrame:
    """`geo_id, name` from the ISO country list (countries) or the state GDP file (states)."""
    if names is None:
        key = "aei_geo_iso" if geo == "country" else "aei_geo_gdp_us_state"
        names = h4.read_income_csv(RAW / by_key(key).dest)
    if geo == "country":
        return names.select(geo_id=pl.col("iso_alpha_3"), name=pl.col("country_name"))
    return names.select(geo_id=pl.lit("US-") + pl.col("state_code"), name=pl.col("state_name"))


def geo_sample_tables(panel: pl.DataFrame, geo: Geo, *, gdp: pl.DataFrame | None = None,
                      wap: pl.DataFrame | None = None, names: pl.DataFrame | None = None
                      ) -> tuple[pl.DataFrame, h4.GeoSample]:
    """The table of `geo_table` and the descriptive (`require_income=False`) sample behind it."""
    full = h4.build_geo_sample(panel, geo=geo, require_income=False, gdp=gdp, wap=wap)
    confirm = h4.build_geo_sample(panel, geo=geo, require_income=True, gdp=gdp, wap=wap)
    split = h4.shift_share(full.frame, full.global_automation, m_global=full.m_global)
    in_h4 = set(confirm.frame["geo_id"])
    t = (full.frame.select("geo_id", "automation_pct", "aui", "mix")
         .join(split.select("geo_id", "gap", "mix_part", "within_part"), on="geo_id")
         .join(_names(geo, names).unique("geo_id"), on="geo_id", how="left")
         .with_columns(name=pl.col("name").fill_null(pl.col("geo_id")),
                       in_h4_sample=pl.col("geo_id").is_in(in_h4))
         .select(TABLE_COLUMNS).sort("geo_id"))
    return t, full


def geo_table(panel: pl.DataFrame, geo: Geo, *, gdp: pl.DataFrame | None = None,
              wap: pl.DataFrame | None = None, names: pl.DataFrame | None = None
              ) -> tuple[pl.DataFrame, float, float]:
    """The shift-share table of every geography with a mix, and `global_automation, m_global`.

    A geography without income stays in the table with `in_h4_sample == False`.
    """
    t, s = geo_sample_tables(panel, geo, gdp=gdp, wap=wap, names=names)
    return t, s.global_automation, s.m_global


def map_values(table: pl.DataFrame, geo: Geo) -> pl.DataFrame:
    """The table with the id column the geometry is joined on (countries: `iso3`, with the
    Natural Earth alias XKX -> KOS; states: `geo_id`)."""
    if geo == "country":
        return table.with_columns(iso3=pl.col("geo_id").replace(NE_ALIAS))
    return table


def unalias(ids: list[str]) -> list[str]:
    """Map Natural Earth ids back to the AEI codes for reporting."""
    back = {v: k for k, v in NE_ALIAS.items()}
    return sorted(back.get(i, i) for i in ids)

