"""Choropleths of countries (Equal Earth) and US states (Albers, with Alaska and Hawaii insets)."""

import geopandas as gpd
import matplotlib.pyplot as plt
import polars as pl
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize, TwoSlopeNorm
from matplotlib.figure import Figure
from matplotlib.patches import Patch

from aideleg.config import RAW
from aideleg.figures.style import FIGSIZE, MISSING_COLOR, apply_style

NE_SHP = RAW / "geo/ne_50m_admin_0_countries/ne_50m_admin_0_countries.shp"
STATES_SHP = RAW / "geo/cb_2023_us_state_20m/cb_2023_us_state_20m.shp"
EQUAL_EARTH = "EPSG:8857"
US_ALBERS = "EPSG:5070"
TERRITORIES = {"PR", "GU", "VI", "AS", "MP"}
MISSING_LABEL = "not published"
_EDGE = {"edgecolor": "white", "linewidth": 0.25}


def load_countries() -> gpd.GeoDataFrame:
    """Natural Earth 50m countries: `iso3` (ISO_A3_EH, else ADM0_A3), `name`, `geometry`.

    ISO_A3_EH gives a few dependencies their sovereign's code (Indian Ocean Territories and
    Ashmore and Cartier Islands carry AUS). Where a code is shared, only the row whose own
    ADM0_A3 equals it keeps it; the others keep their ADM0_A3, so `iso3` is unique.
    """
    raw = gpd.read_file(NE_SHP)
    iso3 = raw["ISO_A3_EH"].where(raw["ISO_A3_EH"] != "-99", raw["ADM0_A3"])
    shared = iso3.duplicated(keep=False) & (iso3 != raw["ADM0_A3"])
    iso3 = iso3.where(~shared, raw["ADM0_A3"])
    out = gpd.GeoDataFrame({"iso3": iso3, "name": raw["NAME"]}, geometry=raw.geometry,
                           crs=raw.crs)
    return out[out["iso3"] != "ATA"].to_crs("EPSG:4326").reset_index(drop=True)


def load_us_states() -> gpd.GeoDataFrame:
    """Census 1:20m states: `geo_id` ("US-" + postal code), `name`, `geometry`; 50 states + DC."""
    raw = gpd.read_file(STATES_SHP)
    raw = raw[~raw["STUSPS"].isin(TERRITORIES)]
    out = gpd.GeoDataFrame({"geo_id": "US-" + raw["STUSPS"], "name": raw["NAME"]},
                           geometry=raw.geometry, crs=raw.crs)
    return out.reset_index(drop=True)


def _norm(vals, center: float | None):
    if len(vals) == 0:
        return Normalize(0.0, 1.0)
    lo, hi = float(min(vals)), float(max(vals))
    if center is None:
        return Normalize(lo, hi)
    span = max(hi - center, center - lo, 1e-12)  # TwoSlopeNorm needs lo < center < hi
    return TwoSlopeNorm(vcenter=center, vmin=min(lo, center - span * 1e-6 if lo >= center else lo),
                        vmax=max(hi, center + span * 1e-6 if hi <= center else hi))


def _paint(ax, frame: gpd.GeoDataFrame, value_col: str, cmap: str, norm) -> None:
    have = frame[frame[value_col].notna()]
    miss = frame[frame[value_col].isna()]
    if len(miss):
        miss.plot(ax=ax, color=MISSING_COLOR, **_EDGE)
    if len(have):
        have.plot(ax=ax, column=value_col, cmap=cmap, norm=norm, **_EDGE)
    ax.set_axis_off()
    ax.set_aspect("equal")


def choropleth(gdf: gpd.GeoDataFrame, values: pl.DataFrame, *, id_col: str, value_col: str,
               title: str, cmap: str, center: float | None = None,
               label: str) -> tuple[Figure, list[str]]:
    """Fill `gdf` by `values[value_col]`, joined on `id_col`.

    Areas without a value are drawn in MISSING_COLOR ("not published"). Returns the figure and
    the sorted ids of `values` that matched no geometry; they are never dropped silently.
    """
    apply_style()
    ids = values[id_col].to_list()
    unmatched = sorted(set(ids) - set(gdf[id_col]))
    vals = values.select([id_col, value_col]).to_pandas()
    frame = gdf.merge(vals, on=id_col, how="left")
    norm = _norm(frame[value_col].dropna().to_list(), center)
    us = bool(len(frame)) and frame[id_col].str.startswith("US-").all()

    fig = plt.figure(figsize=FIGSIZE["map"])
    ax = fig.add_axes((0.02, 0.16, 0.96, 0.76))
    if us:
        frame = frame.to_crs(US_ALBERS)
        is_inset = frame[id_col].isin(["US-AK", "US-HI"])
        _paint(ax, frame[~is_inset], value_col, cmap, norm)
        for sid, rect in (("US-AK", (0.03, 0.16, 0.22, 0.28)), ("US-HI", (0.26, 0.16, 0.12, 0.16))):
            part = frame[frame[id_col] == sid]
            if len(part):
                _paint(fig.add_axes(rect), part, value_col, cmap, norm)
        legend_loc = "lower right"
    else:
        _paint(ax, frame.to_crs(EQUAL_EARTH), value_col, cmap, norm)
        legend_loc = "lower left"
    ax.set_title(title)
    if frame[value_col].isna().any():
        ax.legend(handles=[Patch(facecolor=MISSING_COLOR, label=MISSING_LABEL)],
                  loc=legend_loc, bbox_to_anchor=(1.0 if us else 0.0, -0.06),
                  frameon=False)
    cax = fig.add_axes((0.35, 0.07, 0.3, 0.03))
    fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal",
                 label=label)
    return fig, unmatched
