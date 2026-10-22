"""H4 (PAP §4.4, D16, D17). Synthetic data only; nothing here reads AEI outcomes."""

import datetime as dt
import math

import numpy as np
import polars as pl
import pytest
import statsmodels.api as sm

from aideleg.config import SEED
from aideleg.rq1 import h4

APR, MAY = dt.date(2026, 4, 1), dt.date(2026, 5, 1)
END = {APR: dt.date(2026, 5, 1), MAY: dt.date(2026, 6, 1)}


def _row(period, geo_level, geo_id, taxonomy, node_id, metric, value, release="r6",
         source="claude_ai"):
    return {"release": release, "period_start": period, "period_end": END[period],
            "source": source, "geo_level": geo_level, "geo_id": geo_id, "taxonomy": taxonomy,
            "level": 0, "node_id": node_id, "node_name": node_id, "metric": metric,
            "value": None if value is None else float(value), "definition": "collab_v2"}


def _overall(geo_level, geo_id, months: dict, **kw):
    """`months` maps a period to {metric: value}."""
    return [_row(p, geo_level, geo_id, "overall", "overall", m, v, **kw)
            for p, vals in months.items() for m, v in vals.items()]


def _gwa(geo_level, geo_id, months: dict, metric="pct", taxonomy="onet_gwa", **kw):
    """`months` maps a period to {node: value}."""
    return [_row(p, geo_level, geo_id, taxonomy, g, metric, v, **kw)
            for p, vals in months.items() for g, v in vals.items()]


def _panel(rows) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={
        "release": pl.String, "period_start": pl.Date, "period_end": pl.Date,
        "source": pl.String, "geo_level": pl.String, "geo_id": pl.String,
        "taxonomy": pl.String, "level": pl.Int64, "node_id": pl.String, "node_name": pl.String,
        "metric": pl.String, "value": pl.Float64, "definition": pl.String})


def _global(a_bar: dict, pct: dict | None = None, automation=50.0):
    """Global overall rows and global GWA pct/automation (same in both months)."""
    pct = pct or {g: 100.0 / len(a_bar) for g in a_bar}
    rows = _overall("global", "GLOBAL", {p: {"automation_pct": automation, "usage_pct": 100.0,
                                             "usage_per_capita_index": 1.0} for p in (APR, MAY)})
    rows += _gwa("global", "GLOBAL", {p: pct for p in (APR, MAY)})
    rows += _gwa("global", "GLOBAL", {p: {g: a for g, a in a_bar.items() if a is not None}
                                      for p in (APR, MAY)}, metric="automation_pct")
    return rows


def _country(iso, automation=(60.0, 60.0), aui=(1.0, 1.0), gwa=None, **extra):
    months = {}
    for i, p in enumerate((APR, MAY)):
        vals = {"automation_pct": automation[i], "usage_per_capita_index": aui[i],
                "usage_pct": 1.0, "validation_pct": 10.0 + i, "ai_autonomy_mean": 3.0}
        vals.update({k: v[i] for k, v in extra.items()})
        months[p] = {k: v for k, v in vals.items() if v is not None}
    rows = _overall("country", iso, months)
    rows += _gwa("country", iso, gwa or {APR: {"g1": 50.0, "g2": 50.0},
                                         MAY: {"g1": 50.0, "g2": 50.0}})
    return rows


def _income_csvs(isos, *, codes=None):
    codes = codes or {}
    gdp = pl.DataFrame({"iso_alpha_3": list(isos), "gdp_total": ["1000000.0"] * len(isos),
                        "year": ["2024"] * len(isos)})
    wap = pl.DataFrame({"iso_alpha_3": list(isos), "year": ["2024"] * len(isos),
                        "working_age_pop": ["100.0"] * len(isos),
                        "country_code": [codes.get(i, i[:2]) for i in isos],
                        "country_name": list(isos)})
    return gdp, wap


def _sample(rows, isos, **kw):
    gdp, wap = _income_csvs(isos)
    return h4.build_geo_sample(_panel(rows), gdp=gdp, wap=wap, **kw)


def test_mix_control_hand_case():
    gwa = {APR: {"g1": 30.0, "g2": 10.0}, MAY: {"g1": 20.0, "g2": 20.0}}
    rows = _global({"g1": 40.0, "g2": 80.0}) + _country("AAA", gwa=gwa)
    s = _sample(rows, ["AAA"])
    assert s.frame["mix"].to_list() == pytest.approx([55.0], abs=1e-12)
    rows = _global({"g1": 40.0, "g2": None}) + _country("AAA", gwa=gwa)
    s = _sample(rows, ["AAA"])
    assert s.frame["mix"].to_list() == pytest.approx([40.0], abs=1e-12)


def test_global_automation_and_m_global():
    rows = _global({"g1": 40.0, "g2": 80.0}, pct={"g1": 75.0, "g2": 25.0}, automation=52.0)
    rows += _country("AAA")
    s = _sample(rows, ["AAA"])
    assert s.global_automation == pytest.approx(52.0)
    assert s.m_global == pytest.approx(0.75 * 40 + 0.25 * 80)


def test_logs_of_two_month_means():
    rows = _global({"g1": 40.0, "g2": 80.0}) + _country("AAA", aui=(1.0, 3.0),
                                                        automation=(40.0, 60.0))
    f = _sample(rows, ["AAA"]).frame
    assert f["aui"][0] == pytest.approx(2.0)
    assert f["log_aui"][0] == pytest.approx(math.log(2))
    assert f["automation_pct"][0] == pytest.approx(50.0)
    assert f["log_income"][0] == pytest.approx(math.log(1_000_000 / 100))
    assert f["validation_pct"][0] == pytest.approx(10.5)


def test_country_join_keeps_namibia(tmp_path):
    gdp = tmp_path / "gdp.csv"
    wap = tmp_path / "wap.csv"
    gdp.write_text("iso_alpha_3,gdp_total,year\nNAM,13370000000.0,2024\n"
                   "AAA,NA,2024\n")
    wap.write_text("iso_alpha_3,year,working_age_pop,country_code,country_name\n"
                   "NAM,2024,1798301.0,NA,Namibia\nAAA,2024,100.0,AA,Aland\n")
    rows = _global({"g1": 40.0, "g2": 80.0}) + _country("NAM") + _country("AAA")
    s = h4.build_geo_sample(_panel(rows), gdp=h4.read_income_csv(gdp),
                            wap=h4.read_income_csv(wap))
    assert s.frame["geo_id"].to_list() == ["NAM"]
    assert s.frame["income"][0] == pytest.approx(13370000000.0 / 1798301.0)
    assert s.excluded["missing_income"] == ["AAA"]
    kept = h4.build_geo_sample(_panel(rows), gdp=h4.read_income_csv(gdp),
                               wap=h4.read_income_csv(wap), require_income=False)
    assert kept.frame["geo_id"].to_list() == ["AAA", "NAM"]
    assert kept.frame["income"].to_list()[0] is None


def test_missing_month_excluded_and_listed():
    rows = (_global({"g1": 40.0, "g2": 80.0}) + _country("AAA")
            + _country("BBB", automation=(60.0, None)) + _country("CCC", aui=(None, 2.0)))
    s = _sample(rows, ["AAA", "BBB", "CCC"])
    assert s.frame["geo_id"].to_list() == ["AAA"]
    assert s.excluded["missing_month"] == ["BBB", "CCC"]


def test_missing_mix_excluded_and_listed():
    rows = _global({"g1": 40.0, "g2": 80.0}) + _country("AAA")
    rows += [r for r in _country("BBB") if r["taxonomy"] == "overall"]
    s = _sample(rows, ["AAA", "BBB"])
    assert s.excluded["missing_mix"] == ["BBB"]


def _synthetic(n=60, seed=SEED):
    rng = np.random.default_rng(seed)
    log_aui = rng.normal(0.0, 1.0, n)
    log_income = rng.normal(10.0, 1.0, n)
    mix = rng.normal(50.0, 5.0, n)
    y = 50 + 2 * log_aui - 1 * log_income + 0.5 * mix + rng.normal(0.0, 1.0, n)
    return pl.DataFrame({"geo_id": [f"C{i:02d}" for i in range(n)], "automation_pct": y,
                         "log_aui": log_aui, "log_income": log_income, "mix": mix,
                         "usage_pct": rng.uniform(0.1, 2.0, n),
                         "validation_pct": 20 + rng.normal(0.0, 1.0, n)})


def test_h4_recovers_planted_coefficients_and_df():
    res = h4.estimate_h4(_synthetic())
    assert res.hypothesis == "H4"
    assert res.coefs["log_aui"].estimate == pytest.approx(2.0, abs=0.3)
    assert res.coefs["log_income"].estimate == pytest.approx(-1.0, abs=0.3)
    assert set(res.coefs) == {"log_aui", "log_income", "mix"}
    assert res.diagnostics["df_num"] == 2
    assert res.diagnostics["df_denom"] == 56
    assert res.sample["n"] == 60
    for c in res.coefs.values():
        assert c.df is None and c.ci_low < c.estimate < c.ci_high
    res.to_dict()


def test_h4_p_is_joint_wald():
    f = _synthetic()
    res = h4.estimate_h4(f)
    X = sm.add_constant(f.select("log_aui", "log_income", "mix").to_numpy())
    fit = sm.OLS(f["automation_pct"].to_numpy(), X).fit(cov_type="HC3")
    R = np.array([[0, 1, 0, 0], [0, 0, 1, 0]])
    w = fit.wald_test(R, use_f=True, scalar=True)
    assert res.p_family == pytest.approx(float(w.pvalue), rel=1e-12)
    assert res.diagnostics["F"] == pytest.approx(float(w.statistic), rel=1e-12)
    assert res.coefs["log_aui"].p == pytest.approx(float(fit.pvalues[1]), rel=1e-12)
    assert res.coefs["mix"].se == pytest.approx(float(fit.bse[3]), rel=1e-12)


def test_h4_weights_use_wls():
    f = _synthetic()
    res = h4.estimate_h4(f, weights="usage_pct")
    X = sm.add_constant(f.select("log_aui", "log_income", "mix").to_numpy())
    fit = sm.WLS(f["automation_pct"].to_numpy(), X,
                 weights=f["usage_pct"].to_numpy()).fit(cov_type="HC3")
    assert res.coefs["log_aui"].estimate == pytest.approx(float(fit.params[1]), rel=1e-12)


def test_h4_rejects_null_regressor():
    f = _synthetic().with_columns(log_income=pl.when(pl.col("geo_id") == "C00")
                                  .then(None).otherwise(pl.col("log_income")))
    with pytest.raises(ValueError, match="log_income"):
        h4.estimate_h4(f)


def test_shift_share_identity():
    f = pl.DataFrame({"geo_id": ["AAA"], "automation_pct": [60.0], "mix": [55.0]})
    out = h4.shift_share(f, 50.0)
    assert out.columns == ["geo_id", "gap", "mix_part", "within_part"]
    assert out.row(0) == ("AAA", 10.0, 5.0, 5.0)
    rng = np.random.default_rng(SEED)
    for _ in range(20):
        r = pl.DataFrame({"geo_id": [str(i) for i in range(30)],
                          "automation_pct": rng.uniform(0, 100, 30),
                          "mix": rng.uniform(0, 100, 30)})
        g = float(rng.uniform(0, 100))
        s = h4.shift_share(r, g)
        assert np.allclose(s["mix_part"] + s["within_part"], s["gap"], rtol=0, atol=1e-12)


def test_us_state_geo():
    rows = _global({"g1": 40.0, "g2": 80.0})
    for st in ("US-CA", "US-TX"):
        rows += [{**r, "geo_level": "subregion"} for r in _country(st)]
    rows += [{**r, "geo_level": "subregion"} for r in _country("FR-75")]
    gdp = pl.DataFrame({"state_code": ["CA", "TX"], "state_name": ["California", "Texas"],
                        "gdp_total": ["4.0e12", "2.5e12"], "gdp_millions": ["4e6", "2.5e6"],
                        "year": ["2024", "2024"]})
    wap = pl.DataFrame({"state": ["California", "Texas"],
                        "working_age_pop": ["25000000", "19000000"],
                        "state_code": ["CA", "TX"]})
    s = h4.build_geo_sample(_panel(rows), geo="us_state", gdp=gdp, wap=wap)
    assert s.frame["geo_id"].to_list() == ["US-CA", "US-TX"]
    assert s.frame["income"][0] == pytest.approx(4.0e12 / 25_000_000)


def test_outcome_is_an_argument():
    res = h4.estimate_h4(_synthetic(), outcome="validation_pct")
    assert res.outcome == "validation_pct"
    assert res.diagnostics["df_denom"] == 56


def test_release_without_country_aui_raises():
    rows = _global({"g1": 40.0, "g2": 80.0})
    rows += [r for r in _country("AAA") if r["metric"] != "usage_per_capita_index"]
    with pytest.raises(ValueError, match="usage_per_capita_index"):
        _sample(rows, ["AAA"])


def test_release_without_country_gwa_raises():
    rows = _global({"g1": 40.0, "g2": 80.0})
    rows += [r for r in _country("AAA") if r["taxonomy"] == "overall"]
    with pytest.raises(ValueError, match="onet_gwa"):
        _sample(rows, ["AAA"])


def test_r5_country_raises():
    rows = [{**r, "release": "r5"} for r in _global({"g1": 40.0}) + _country("AAA")
            if r["metric"] != "usage_per_capita_index"]
    with pytest.raises(ValueError, match="usage_per_capita_index"):
        _sample(rows, ["AAA"], release="r5")


def test_iwa_mix_level():
    rows = _global({"g1": 40.0, "g2": 80.0})
    rows += _gwa("global", "GLOBAL", {p: {"i1": 50.0, "i2": 50.0} for p in (APR, MAY)},
                 taxonomy="onet_iwa")
    rows += _gwa("global", "GLOBAL", {p: {"i1": 10.0, "i2": 30.0} for p in (APR, MAY)},
                 taxonomy="onet_iwa", metric="automation_pct")
    rows += _country("AAA")
    rows += _gwa("country", "AAA", {p: {"i1": 1.0, "i2": 3.0} for p in (APR, MAY)},
                 taxonomy="onet_iwa")
    s = _sample(rows, ["AAA"], mix_level="iwa")
    assert s.frame["mix"][0] == pytest.approx(0.25 * 10 + 0.75 * 30)
