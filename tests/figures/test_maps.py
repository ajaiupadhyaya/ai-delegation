import geopandas as gpd
import matplotlib.pyplot as plt
import polars as pl
import pytest
from matplotlib.colors import TwoSlopeNorm, to_hex
from shapely.geometry import box

from aideleg.figures import MISSING_COLOR, maps

GDF = gpd.GeoDataFrame({"iso3": ["AAA", "BBB"], "name": ["a", "b"]},
                       geometry=[box(0, 0, 10, 10), box(20, 0, 30, 10)], crs="EPSG:4326")


def _colours(fig):
    return {to_hex(c) for col in fig.axes[0].collections for c in col.get_facecolor()}


def test_choropleth_reports_unmatched_ids():
    vals = pl.DataFrame({"iso3": ["AAA", "ZZZ"], "v": [1.0, 2.0]})
    fig, unmatched = maps.choropleth(GDF, vals, id_col="iso3", value_col="v", title="t",
                                     cmap="viridis", label="l")
    assert unmatched == ["ZZZ"]
    assert to_hex(MISSING_COLOR) in _colours(fig)  # BBB has no value
    texts = [t.get_text() for t in fig.axes[0].get_legend().get_texts()]
    assert texts == ["not published"]
    plt.close(fig)


def test_choropleth_center_uses_two_slope_norm():
    vals = pl.DataFrame({"iso3": ["AAA", "BBB"], "v": [-2.0, 6.0]})
    fig, unmatched = maps.choropleth(GDF, vals, id_col="iso3", value_col="v", title="t",
                                     cmap="PuOr", center=0.0, label="l")
    assert unmatched == []
    norm = [c for c in fig.axes[0].collections if c.get_array() is not None][0].norm
    assert isinstance(norm, TwoSlopeNorm)
    assert (norm.vcenter, norm.vmin, norm.vmax) == (0.0, -2.0, 6.0)
    assert to_hex(MISSING_COLOR) not in _colours(fig)
    assert fig.axes[0].get_legend() is None
    plt.close(fig)
    fig, _ = maps.choropleth(GDF, vals, id_col="iso3", value_col="v", title="t",
                             cmap="viridis", label="l")
    norm = [c for c in fig.axes[0].collections if c.get_array() is not None][0].norm
    assert not isinstance(norm, TwoSlopeNorm)
    plt.close(fig)


def test_center_outside_the_data_range_does_not_raise():
    vals = pl.DataFrame({"iso3": ["AAA", "BBB"], "v": [1.0, 3.0]})
    fig, _ = maps.choropleth(GDF, vals, id_col="iso3", value_col="v", title="t",
                             cmap="PuOr", center=0.0, label="l")
    plt.close(fig)


@pytest.mark.data
def test_real_geometries_load():
    c = maps.load_countries()
    assert list(c.columns) == ["iso3", "name", "geometry"]
    assert len(c) >= 230 and {"NAM", "SGP"} <= set(c["iso3"]) and "ATA" not in set(c["iso3"])
    assert c["iso3"].is_unique and c.crs == "EPSG:4326"
    s = maps.load_us_states()
    assert list(s.columns) == ["geo_id", "name", "geometry"]
    assert len(s) == 51 and {"US-DC", "US-AK", "US-HI"} <= set(s["geo_id"])
    assert "US-PR" not in set(s["geo_id"])


@pytest.mark.data
def test_real_us_map_draws_with_insets():
    s = maps.load_us_states()
    vals = pl.DataFrame({"geo_id": [g for g in s["geo_id"] if g != "US-WY"] + ["US-XX"],
                         "v": [float(i) for i in range(51)]})
    fig, unmatched = maps.choropleth(s, vals, id_col="geo_id", value_col="v", title="t",
                                     cmap="viridis", label="l")
    assert unmatched == ["US-XX"] and len(fig.axes) == 4  # main, AK, HI, colourbar
    plt.close(fig)


def test_all_text_inside_canvas_with_long_label_and_legend():
    vals = pl.DataFrame({"iso3": ["AAA"], "v": [1.0]})  # BBB unpublished -> legend
    fig, _ = maps.choropleth(
        GDF, vals, id_col="iso3", value_col="v", title="A long map title, countries",
        cmap="PuOr", center=0.0, ticks=[0.5, 1.0], ticklabels=["a", "b"], clip=(2, 98),
        label="AUI (log scale; 1 = share of usage equals share of working-age population)")
    box = fig.get_tightbbox(fig.canvas.get_renderer())
    w, h = fig.get_size_inches()
    assert box.x0 >= -1e-6 and box.y0 >= -1e-6 and box.x1 <= w + 1e-6 and box.y1 <= h + 1e-6
    plt.close(fig)
