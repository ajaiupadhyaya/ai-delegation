"""Choropleths of countries (Equal Earth) and US states (Albers, with Alaska and Hawaii insets)."""

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
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


def _norm(vals, center: float | None, clip: tuple[float, float] | None = None):
    if len(vals) == 0:
        return Normalize(0.0, 1.0)
    lo, hi = float(min(vals)), float(max(vals))
    if clip is not None:
        lo, hi = (float(x) for x in np.percentile(vals, clip))
    if center is None:
        return Normalize(lo, hi)
    span = max(hi - center, center - lo, 1e-12)  # TwoSlopeNorm needs lo < center < hi
    return TwoSlopeNorm(vcenter=center, vmin=min(lo, center - span * 1e-6 if lo >= center else lo),
                        vmax=max(hi, center + span * 1e-6 if hi <= center else hi))


def _paint(ax, frame: gpd.GeoDataFrame, value_col: str, cmap: str, norm,
           edgecolor: str = "white") -> None:
    edge = {"edgecolor": edgecolor, "linewidth": 0.25, "rasterized": True}
    have = frame[frame[value_col].notna()]
    miss = frame[frame[value_col].isna()]
    if len(miss):
        miss.plot(ax=ax, color=MISSING_COLOR, **edge)
    if len(have):
        have.plot(ax=ax, column=value_col, cmap=cmap, norm=norm, **edge)
    ax.set_axis_off()
    ax.set_aspect("equal")


def _frame_inset(ax, label: str) -> None:
    """A thin frame and a short label round an inset."""
    ax.set_axis_on()
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(True)
        sp.set_linewidth(0.4)
        sp.set_color("0.5")
    ax.text(0.05, 0.92, label, transform=ax.transAxes, fontsize=7, va="top")


def choropleth(gdf: gpd.GeoDataFrame, values: pl.DataFrame, *, id_col: str, value_col: str,
               title: str, cmap: str, center: float | None = None,
               label: str, ticks: list[float] | None = None,
               ticklabels: list[str] | None = None,
               clip: tuple[float, float] | None = None,
               edgecolor: str = "white") -> tuple[Figure, list[str]]:
    """Fill `gdf` by `values[value_col]`, joined on `id_col`.

    Areas without a value are drawn in MISSING_COLOR ("not published"). Returns the figure and
    the sorted ids of `values` that matched no geometry; they are never dropped silently.
    `ticks`/`ticklabels` set the colourbar ticks (for a transformed scale); `clip` is a pair of
    percentiles at which the colour scale is cut (the bar then shows arrow ends).
    """
    apply_style()
    ids = values[id_col].to_list()
    unmatched = sorted(set(ids) - set(gdf[id_col]))
    vals = values.select([id_col, value_col]).to_pandas()
    frame = gdf.merge(vals, on=id_col, how="left")
    data = frame[value_col].dropna().to_list()
    norm = _norm(data, center, clip)
    us = bool(len(frame)) and frame[id_col].str.startswith("US-").all()

    fig = plt.figure(figsize=FIGSIZE["map"])
    ax = fig.add_axes((0.02, 0.20, 0.96, 0.68))
    if us:
        frame = frame.to_crs(US_ALBERS)
        is_inset = frame[id_col].isin(["US-AK", "US-HI"])
        _paint(ax, frame[~is_inset], value_col, cmap, norm, edgecolor)
        for sid, rect in (("US-AK", (0.03, 0.20, 0.22, 0.26)), ("US-HI", (0.27, 0.20, 0.12, 0.14))):
            part = frame[frame[id_col] == sid]
            if len(part):
                inset = fig.add_axes(rect)
                _paint(inset, part, value_col, cmap, norm, edgecolor)
                _frame_inset(inset, sid[3:])
    else:
        _paint(ax, frame.to_crs(EQUAL_EARTH), value_col, cmap, norm, edgecolor)
    ax.set_title(title, pad=6)
    cax = fig.add_axes((0.30, 0.07, 0.40, 0.025))
    below = bool(data) and min(data) < norm.vmin
    above = bool(data) and max(data) > norm.vmax
    extend = "both" if below and above else "min" if below else "max" if above else "neither"
    cb = fig.colorbar(ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal",
                      extend=extend)
    if ticks is not None:
        keep = [i for i, t in enumerate(ticks) if norm.vmin <= t <= norm.vmax]
        cb.set_ticks([ticks[i] for i in keep],
                     labels=[ticklabels[i] for i in keep] if ticklabels else None)
    cb.ax.set_title(label, fontsize=8, pad=4)
    if frame[value_col].isna().any():
        ax.legend(handles=[Patch(facecolor=MISSING_COLOR, label=MISSING_LABEL)],
                  loc="center left", bbox_to_anchor=(0.73, 0.083),
                  bbox_transform=fig.transFigure, frameon=False)
    return fig, unmatched
