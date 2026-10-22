"""RQ1 geography: shift-share split and map specs. Synthetic inputs only."""

import polars as pl
import synth

from aideleg.describe import geography
from aideleg.figures.save import _NAME

ISO = pl.DataFrame({"iso_alpha_2": ["AR", "AU"], "iso_alpha_3": ["ARG", "AUS"],
                    "country_name": ["Argentina", "Australia"]})


def _inputs():
    return synth.synthetic_inputs()


def test_geo_table_identity():
    inp = _inputs()
    t, g, m = geography.geo_table(inp.panel, "country", gdp=inp.gdp_country,
                                  wap=inp.wap_country, names=ISO)
    assert t.height == len(synth.SYNTH_COUNTRIES)
    assert t.columns == ["geo_id", "name", "automation_pct", "aui", "mix", "gap", "mix_part",
                         "within_part", "in_h4_sample"]
    diff = (t["mix_part"] + t["within_part"] - t["gap"]).abs().max()
    assert diff < 1e-12
    assert t.filter(pl.col("geo_id") == "ARG")["name"].item() == "Argentina"
    assert t.filter(pl.col("geo_id") == "BRA")["name"].item() == "BRA"  # no name: id kept
    assert (t["gap"] - (t["automation_pct"] - g)).abs().max() < 1e-12
    assert (t["mix_part"] - (t["mix"] - g)).abs().max() < 1e-12
    assert m != g  # the offset the report prints is not zero here


def test_in_h4_sample_flag():
    inp = _inputs()
    gdp = inp.gdp_country.filter(pl.col("iso_alpha_3") != "BRA")
    t, _, _ = geography.geo_table(inp.panel, "country", gdp=gdp, wap=inp.wap_country, names=ISO)
    row = t.filter(pl.col("geo_id") == "BRA")
    assert row.height == 1 and row["in_h4_sample"].item() is False
    assert row["mix_part"].item() is not None
    assert t.filter(pl.col("geo_id") != "BRA")["in_h4_sample"].all()


def test_map_specs_cover_both_geographies():
    names = [s.fig_name for geo in geography.MAPS.values() for s in geo]
    assert len(names) == 8 and len(set(names)) == 8
    assert all(_NAME.fullmatch(n) for n in names)
    assert set(names) == {f"fig_rq1_map_{g}_{v}" for g in ("country", "state")
                          for v in ("automation", "aui", "mix", "within")}
    by_var = {s.column: s for s in geography.MAPS["country"]}
    assert by_var["aui"].log and by_var["aui"].center == 0 and by_var["mix_part"].center == 0
    assert by_var["within_part"].center == 0 and by_var["automation_pct"].center is None


def test_state_ids_prefixed():
    inp = _inputs()
    panel = inp.panel
    apr = panel.filter((pl.col("geo_level") == "country") & pl.col("geo_id").is_in(["ARG", "AUS"]))
    st = apr.with_columns(
        geo_level=pl.lit("subregion"),
        geo_id=pl.when(pl.col("geo_id") == "ARG").then(pl.lit("US-CA")).otherwise(pl.lit("US-TX")))
    panel = pl.concat([panel, st])
    gdp = pl.DataFrame({"state_code": ["CA", "TX"], "state_name": ["California", "Texas"],
                        "gdp_total": ["4.0e12", "2.5e12"], "year": ["2024", "2024"]})
    wap = pl.DataFrame({"state_code": ["CA", "TX"], "working_age_pop": ["25000000", "19000000"]})
    t, _, _ = geography.geo_table(panel, "us_state", gdp=gdp, wap=wap, names=gdp)
    assert t.height == 2 and all(i.startswith("US-") for i in t["geo_id"])
    assert t["name"].to_list() == ["California", "Texas"]


def test_choropleth_ids_alias_kosovo():
    t = pl.DataFrame({"geo_id": ["XKX", "ARG"], "v": [1.0, 2.0]})
    out = geography.map_values(t, "country")
    assert out["iso3"].to_list() == ["KOS", "ARG"]
    assert "iso3" not in geography.map_values(t, "us_state").columns
    assert geography.unalias(["KOS"]) == ["XKX"]



def _report_inputs():
    from datetime import date

    import geopandas as gpd
    from shapely.geometry import box

    inp = _inputs()
    panel = inp.panel.filter(~((pl.col("geo_id") == "NAM") & (pl.col("metric") == "automation_pct")
                               & (pl.col("period_start") == date(2026, 5, 1))))
    st = panel.filter((pl.col("geo_level") == "country") & pl.col("geo_id").is_in(["ARG", "AUS"])
                      ).with_columns(
        geo_level=pl.lit("subregion"),
        geo_id=pl.when(pl.col("geo_id") == "ARG").then(pl.lit("US-CA")).otherwise(pl.lit("US-TX")))
    panel = pl.concat([panel, st])
    sgdp = pl.DataFrame({"state_code": ["CA", "TX"], "state_name": ["California", "Texas"],
                         "gdp_total": ["4.0e12", "2.5e12"], "year": ["2024", "2024"]})
    swap = pl.DataFrame({"state_code": ["CA", "TX"], "working_age_pop": ["25000000", "19000000"]})
    countries = gpd.GeoDataFrame(
        {"iso3": list(synth.SYNTH_COUNTRIES), "name": list(synth.SYNTH_COUNTRIES)},
        geometry=[box(10 * i, 0, 10 * i + 8, 8) for i in range(len(synth.SYNTH_COUNTRIES))],
        crs="EPSG:4326")
    states = gpd.GeoDataFrame({"geo_id": ["US-CA", "US-TX"], "name": ["California", "Texas"]},
                              geometry=[box(-120, 35, -115, 40), box(-100, 28, -95, 33)],
                              crs="EPSG:4326")
    return dict(panel=panel, gdp={"country": inp.gdp_country, "us_state": sgdp},
                wap={"country": inp.wap_country, "us_state": swap},
                names={"country": ISO, "us_state": sgdp}, countries=countries, states=states)


def test_report_geography_marks_one_month_geographies(tmp_path, monkeypatch):
    from aideleg.figures import maps
    from aideleg.results import rq1

    calls = []
    real = maps.choropleth

    def spy(*a, **kw):
        calls.append(kw.get("partial_ids", ()))
        return real(*a, **kw)

    monkeypatch.setattr(maps, "choropleth", spy)
    rq1.report_geography(tmp_path / "o", fig_dir=tmp_path / "f", **_report_inputs())
    md = (tmp_path / "o" / "geography.md").read_text(encoding="utf-8")
    label = "not published in both months (not in the H4 sample)"
    assert f"{label}, `missing_month`: 1 (NAM)" in md
    assert "not published, by reason" not in md
    assert len(calls) == 8
    assert all(list(c) == ["NAM"] for c in calls[:4])  # the four country maps
