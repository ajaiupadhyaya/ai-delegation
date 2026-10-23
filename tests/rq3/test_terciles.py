"""Tercile portfolios (PAP §8.3 D19; Design B secondary, Design A exploratory). Synthetic data
only: 49 industries, month-end calendars, French-style frames in percent."""

import calendar
from datetime import date

import numpy as np
import polars as pl
import pytest
import statsmodels.api as sm

from aideleg.config import SEED
from aideleg.rq3 import data, terciles

NAMES = [f"I{i:02d}" for i in range(49)]
FF5 = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]


def _month_ends(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(date(y, m, calendar.monthrange(y, m)[1]))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _expo(designs=("B", "A_r2", "A_pooled"), z=None, seed: int = 5) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for d in designs:
        zd = rng.standard_normal(len(NAMES)) if z is None else z
        rows += [{"design": d, "ff49": i + 1, "ff49_short": nm,
                  "z_delegation": None if zd[i] is None else float(zd[i]),
                  "z_usage": 0.0, "z_aioe": 0.0} for i, nm in enumerate(NAMES)]
    return pl.DataFrame(rows, schema={"design": pl.String, "ff49": pl.Int64,
                                      "ff49_short": pl.String, "z_delegation": pl.Float64,
                                      "z_usage": pl.Float64, "z_aioe": pl.Float64})


def _chars(rows: list[tuple[date, str, float]]) -> pl.DataFrame:
    """`date, me_date, ff49_short, cap` with me_date set as `data.characteristics` sets it."""
    df = pl.DataFrame(rows, schema={"date": pl.Date, "ff49_short": pl.String, "cap": pl.Float64},
                      orient="row")
    return df.with_columns(me_date=data.me_date_expr("date"))


def _synth(seed: int = 3):
    """Monthly industry returns, FF5+UMD factors, FF3 factors (own smb), characteristics."""
    rng = np.random.default_rng(seed)
    months = _month_ends(date(2022, 11, 30), date(2026, 8, 31))
    n = len(months)
    f = rng.standard_normal((n, len(FF5)))
    rf = np.full(n, 0.3)
    beta = rng.normal(1.0, 0.5, size=(len(FF5), len(NAMES)))
    y = f @ beta + rf[:, None] + 2.0 * rng.standard_normal((n, len(NAMES)))
    ret = pl.DataFrame({"date": months, **{nm: y[:, j] for j, nm in enumerate(NAMES)}})
    ff5 = pl.DataFrame({"date": months, **{c: f[:, j] for j, c in enumerate(FF5)}, "rf": rf})
    ff3 = pl.DataFrame({"date": months, "mkt_rf": f[:, 0],
                        "smb": f[:, 1] + rng.standard_normal(n), "hml": f[:, 2], "rf": rf})
    caps = rng.uniform(1.0, 100.0, size=(n, len(NAMES)))
    chars = _chars([(m, nm, float(caps[i, j])) for i, m in enumerate(months)
                    for j, nm in enumerate(NAMES)])
    return ret, ff5, ff3, chars


def _patch(monkeypatch, ret, ff5, ff3, chars, expo=None):
    monkeypatch.setattr(data, "monthly", lambda weighting="VW": (ret, ff5))
    monkeypatch.setattr(data, "ff3_monthly", lambda: ff3)
    monkeypatch.setattr(data, "characteristics", lambda: chars)
    if expo is None:
        monkeypatch.setattr(data, "exposures", lambda: pytest.fail("exposures() called"))
        monkeypatch.setattr(data, "zero_assigned",
                            lambda: pytest.fail("zero_assigned() called"))
    else:
        monkeypatch.setattr(data, "exposures", lambda: expo)
        monkeypatch.setattr(data, "zero_assigned", lambda: pl.DataFrame({
            "design": ["A_pooled", "A_r2", "B"], "occupations": [1, 1, 1],
            "no_usage": [0, 0, 0], "no_usage_emp_pct": [10.0, 12.0, 12.0]}))


# --- constants -------------------------------------------------------------------------


def test_constants():
    assert terciles.WINDOWS == {"B": (date(2025, 4, 30), date(2026, 8, 31)),
                                "A": (date(2022, 12, 31), date(2026, 8, 31))}
    assert len(terciles.window_months("B")) == 17
    assert len(terciles.window_months("A")) == 45
    assert terciles.VARIANTS == (("B", "cap"), ("B", "ew"), ("A_r2", "cap"), ("A_r2", "ew"),
                                 ("A_pooled", "cap"), ("A_pooled", "ew"))
    assert terciles.COSTS_BPS == (0, 5, 15, 30)
    assert terciles.FORMATION_TURNOVER == 2.0
    assert terciles.MODELS["CAPM"] == ("ff5", ["mkt_rf"])
    assert terciles.MODELS["FF5+UMD"] == ("ff5", FF5)


# --- members ---------------------------------------------------------------------------


def test_members_sizes_16_17_16():
    m = terciles.members(_expo(designs=("B",), z=list(np.linspace(-2, 2, 49))))
    assert [len(m["high"]), len(m["mid"]), len(m["low"])] == [16, 17, 16]
    assert m["high"][0] == "I48" and m["low"][-1] == "I00"
    assert set(m["high"]) | set(m["mid"]) | set(m["low"]) == set(NAMES)


def test_ties_broken_by_ff49():
    z = list(np.linspace(-2, 2, 49))
    # descending order puts I48..I33 in high; tie the 16th (I33) with the 17th (I32)
    z[32] = z[33]
    m = terciles.members(_expo(designs=("B",), z=z))
    assert "I32" in m["high"] and "I33" in m["mid"]


def test_null_exposure_excluded():
    z: list = list(np.linspace(-2, 2, 49))
    z[10] = None
    m = terciles.members(_expo(designs=("B",), z=z))
    assert [len(m["high"]), len(m["mid"]), len(m["low"])] == [16, 16, 16]
    assert "I10" not in m["high"] + m["mid"] + m["low"]


# --- legs ------------------------------------------------------------------------------


def _leg_ret() -> pl.DataFrame:
    return pl.DataFrame({"date": [date(2024, 2, 29)], "I00": [1.0], "I01": [3.0], "I02": [0.0]})


@pytest.mark.parametrize("offset,expected", [(1, 1.5), (0, 2.5)])
def test_cap_weights_use_prior_month_end_me(monkeypatch, offset, expected):
    monkeypatch.setattr(data, "SIZE_ME_OFFSET", offset)
    chars = _chars([(date(2024, 1, 31), "I00", 1.0), (date(2024, 1, 31), "I01", 3.0),
                    (date(2024, 1, 31), "I02", 1.0),
                    (date(2024, 2, 29), "I00", 3.0), (date(2024, 2, 29), "I01", 1.0),
                    (date(2024, 2, 29), "I02", 1.0)])
    legs = {"high": ["I00", "I01"], "mid": [], "low": ["I02"]}
    out = terciles.leg_returns(_leg_ret(), chars, legs, [date(2024, 2, 29)], "cap")
    assert out.columns == ["date", "high", "low", "hml"]
    assert out["high"][0] == pytest.approx(expected)
    assert out["hml"][0] == pytest.approx(expected - 0.0)


def test_ew_weights_are_equal():
    chars = _chars([(date(2024, 2, 29), n, c) for n, c in (("I00", 3.0), ("I01", 1.0),
                                                           ("I02", 1.0))])
    legs = {"high": ["I00", "I01"], "mid": [], "low": ["I02"]}
    out = terciles.leg_returns(_leg_ret(), chars, legs, [date(2024, 2, 29)], "ew")
    assert out["high"][0] == pytest.approx(2.0)


def test_missing_return_reweights_within_leg():
    ret = pl.DataFrame({"date": [date(2024, 2, 29)], "I00": [1.0], "I01": [None],
                        "I02": [4.0], "I03": [0.5]}, schema_overrides={"I01": pl.Float64})
    chars = _chars([(date(2024, 2, 29), n, c) for n, c in (("I00", 1.0), ("I01", 5.0),
                                                           ("I02", 3.0), ("I03", 1.0))])
    legs = {"high": ["I00", "I01", "I02"], "mid": [], "low": ["I03"]}
    out = terciles.leg_returns(ret, chars, legs, [date(2024, 2, 29)], "cap")
    assert out["high"][0] == pytest.approx((1 * 1.0 + 3 * 4.0) / 4)
    assert out["low"][0] == pytest.approx(0.5)


def test_missing_cap_leaves_cap_leg_only():
    chars = _chars([(date(2024, 2, 29), "I00", 1.0), (date(2024, 2, 29), "I01", None),
                    (date(2024, 2, 29), "I02", 1.0)])
    legs = {"high": ["I00", "I01"], "mid": [], "low": ["I02"]}
    cap = terciles.leg_returns(_leg_ret(), chars, legs, [date(2024, 2, 29)], "cap")
    ew = terciles.leg_returns(_leg_ret(), chars, legs, [date(2024, 2, 29)], "ew")
    assert cap["high"][0] == pytest.approx(1.0)
    assert ew["high"][0] == pytest.approx(2.0)


def test_nan_and_zero_cap_leave_cap_leg_and_are_reported():
    ret = pl.DataFrame({"date": [date(2024, 2, 29)], "I00": [1.0], "I01": [3.0],
                        "I02": [5.0], "I03": [0.0]})
    chars = _chars([(date(2024, 2, 29), "I00", 2.0), (date(2024, 2, 29), "I01", float("nan")),
                    (date(2024, 2, 29), "I02", 0.0), (date(2024, 2, 29), "I03", 1.0)])
    legs = {"high": ["I00", "I01", "I02"], "mid": [], "low": ["I03"]}
    cap = terciles.leg_returns(ret, chars, legs, [date(2024, 2, 29)], "cap")
    ew = terciles.leg_returns(ret, chars, legs, [date(2024, 2, 29)], "ew")
    assert cap["high"][0] == pytest.approx(1.0)
    assert ew["high"][0] == pytest.approx(3.0)
    gaps = terciles._gap_lines(ret, chars, {"B": legs}, {"B": [date(2024, 2, 29)]})
    assert gaps[0].endswith("missing return (all legs): none")
    assert gaps[1].endswith("missing cap (cap legs only): I01 2024-02, I02 2024-02")


def test_nan_return_leaves_both_legs_and_is_reported():
    ret = pl.DataFrame({"date": [date(2024, 2, 29)], "I00": [1.0], "I01": [float("nan")],
                        "I02": [0.0]})
    chars = _chars([(date(2024, 2, 29), n, 1.0) for n in ("I00", "I01", "I02")])
    legs = {"high": ["I00", "I01"], "mid": [], "low": ["I02"]}
    for w in ("cap", "ew"):
        assert terciles.leg_returns(ret, chars, legs, [date(2024, 2, 29)], w)["high"][0] == 1.0
    gaps = terciles._gap_lines(ret, chars, {"B": legs}, {"B": [date(2024, 2, 29)]})
    assert gaps[0].endswith("missing return (all legs): I01 2024-02")


def test_empty_leg_raises():
    ret = _leg_ret().with_columns(pl.lit(None, dtype=pl.Float64).alias("I02"))
    chars = _chars([(date(2024, 2, 29), n, 1.0) for n in ("I00", "I01", "I02")])
    legs = {"high": ["I00", "I01"], "mid": [], "low": ["I02"]}
    with pytest.raises(ValueError, match="no valid member"):
        terciles.leg_returns(ret, chars, legs, [date(2024, 2, 29)], "ew")


# --- statistics ------------------------------------------------------------------------


def test_cost_deducted_once_from_first_month():
    h = np.array([1.0, -0.5, 2.0, 0.25])
    assert np.allclose(terciles.costed(h, 30), h - np.array([0.6, 0.0, 0.0, 0.0]))
    assert np.allclose(terciles.costed(h, 0), h)


def _factor_frames(T: int, seed: int = 9) -> dict[str, pl.DataFrame]:
    rng = np.random.default_rng(seed)
    f = rng.standard_normal((T, 6))
    ff5 = pl.DataFrame({c: f[:, j] for j, c in enumerate(FF5)} | {"rf": np.zeros(T)})
    ff3 = pl.DataFrame({"mkt_rf": f[:, 0], "smb": rng.standard_normal(T), "hml": f[:, 2],
                        "rf": np.zeros(T)})
    return {"ff5": ff5, "ff3": ff3}


def test_ff3_alpha_uses_ff3_file():
    assert terciles.MODELS["FF3"] == ("ff3", ["mkt_rf", "smb", "hml"])
    T = 45
    fac = _factor_frames(T)
    rng = np.random.default_rng(1)
    h = 0.4 + fac["ff3"]["smb"].to_numpy() + rng.standard_normal(T)
    st = terciles.tercile_stats(h, fac, np.random.default_rng(SEED))

    def ols_alpha(frame):
        X = sm.add_constant(frame.select("mkt_rf", "smb", "hml").to_numpy())
        return 12 * sm.OLS(h, X).fit().params[0]

    assert st["alpha"]["FF3"]["estimate"] == pytest.approx(ols_alpha(fac["ff3"]))
    assert st["alpha"]["FF3"]["estimate"] != pytest.approx(ols_alpha(fac["ff5"]))


def test_tercile_stats_units_and_costs():
    T = 17
    fac = _factor_frames(T)
    h = np.random.default_rng(2).normal(0.5, 2.0, T)
    st = terciles.tercile_stats(h, fac, np.random.default_rng(SEED))
    assert st["mean"]["estimate"] == pytest.approx(12 * h.mean())
    assert st["sharpe"]["estimate"] == pytest.approx(h.mean() / h.std(ddof=1) * np.sqrt(12))
    assert st["sr_monthly"] == pytest.approx(h.mean() / h.std(ddof=1))
    lo, hi = st["sharpe"]["ci"]
    assert lo < st["sharpe"]["estimate"] < hi
    assert st["costs"][30]["mean"] == pytest.approx(12 * (h.mean() - 0.6 / T))
    assert st["costs"][0]["sharpe"] == pytest.approx(st["sharpe"]["estimate"])
    a = st["alpha"]["CAPM"]
    assert a["ci"][0] < a["estimate"] < a["ci"][1]
    assert 0 <= a["p"] <= 1 and st["T"] == T


# --- run_terciles ----------------------------------------------------------------------


def _expected_cis(ret, ff5, ff3, chars, expo, months_by_key):
    rng = np.random.default_rng(SEED)
    out = {}
    for design, w in terciles.VARIANTS:
        if design not in set(expo["design"].to_list()):
            continue
        key = "B" if design == "B" else "A"
        months = months_by_key[key]
        legs = terciles.members(expo.filter(pl.col("design") == design))
        hml = terciles.leg_returns(ret, chars, legs, months, w)["hml"].to_numpy()
        fac = {"ff5": ff5.filter(pl.col("date").is_in(months)).sort("date"),
               "ff3": ff3.filter(pl.col("date").is_in(months)).sort("date")}
        st = terciles.tercile_stats(hml, fac, rng)
        out[(design, w)] = (st["sharpe"]["ci"], st["mean"]["ci"])
    return out


def test_rng_order_is_variants_order(monkeypatch, tmp_path):
    ret, ff5, ff3, chars = _synth()
    expo = _expo()
    _patch(monkeypatch, ret, ff5, ff3, chars, expo)
    df = terciles.run_terciles(tmp_path)
    exp = _expected_cis(ret, ff5, ff3, chars, expo,
                        {k: terciles.window_months(k) for k in terciles.WINDOWS})
    for (design, w), (sci, mci) in exp.items():
        sub = df.filter((pl.col("design") == design) & (pl.col("weighting") == w))
        s = sub.filter(pl.col("statistic") == "sharpe").row(0, named=True)
        m = sub.filter(pl.col("statistic") == "mean").row(0, named=True)
        assert (s["ci_lo"], s["ci_hi"]) == pytest.approx(sci)
        assert (m["ci_lo"], m["ci_hi"]) == pytest.approx(mci)
    assert df.columns == ["design", "weighting", "statistic", "estimate", "se", "ci_lo",
                          "ci_hi", "p", "T"]
    assert set(df["statistic"]) == {"alpha_CAPM", "alpha_FF3", "alpha_FF5+UMD", "sharpe",
                                    "psr", "dsr", "mean"}
    assert df.height == 6 * 7
    assert df.filter(pl.col("statistic") == "dsr")["estimate"].null_count() == 0
    assert set(df.filter(pl.col("design") == "B")["T"]) == {17}
    assert set(df.filter(pl.col("design") != "B")["T"]) == {45}
    md = (tmp_path / "terciles.md").read_text()
    assert md.startswith("# Tercile portfolios (exploratory, PAP §8.3 D19; Design B rows are "
                         "secondary)")
    assert "measurement devices, not strategies" in md
    assert "look-ahead" in md
    assert "12.00% (D3)" in md
    assert (tmp_path / "terciles.csv").exists()


def test_run_terciles_months_and_expo(monkeypatch, tmp_path):
    ret, ff5, ff3, chars = _synth()
    _patch(monkeypatch, ret, ff5, ff3, chars, expo=None)
    expo = _expo(designs=("A_r2", "A_pooled"))
    a_months = [m for m in terciles.window_months("A") if m.year != 2023]
    seen: list = []
    real = terciles.leg_returns

    def spy(monthly_ret, chars_, legs, months, weighting):
        seen.append(list(months))
        return real(monthly_ret, chars_, legs, months, weighting)

    monkeypatch.setattr(terciles, "leg_returns", spy)
    df = terciles.run_terciles(tmp_path, months={"A": a_months}, expo=expo)
    assert set(df["design"]) == {"A_r2", "A_pooled"}
    assert len(seen) == 4
    assert all(m.year != 2023 for ms in seen for m in ms)
    assert set(df["T"]) == {33}


def test_run_terciles_refuses_months_outside_window(monkeypatch, tmp_path):
    ret, ff5, ff3, chars = _synth()
    _patch(monkeypatch, ret, ff5, ff3, chars, expo=None)
    with pytest.raises(ValueError, match="outside"):
        terciles.run_terciles(tmp_path, months={"B": [date(2025, 3, 31)]},
                              expo=_expo(designs=("B",)))


def test_dsr_over_the_variants_run(monkeypatch, tmp_path):
    from aideleg.rq3 import stats

    ret, ff5, ff3, chars = _synth()
    _patch(monkeypatch, ret, ff5, ff3, chars, expo=None)
    expo = _expo(designs=("B",))
    df = terciles.run_terciles(tmp_path, expo=expo)
    months = terciles.window_months("B")
    legs = terciles.members(expo)
    h = {w: terciles.leg_returns(ret, chars, legs, months, w)["hml"].to_numpy()
         for w in ("cap", "ew")}
    srs = [stats.sr(h["cap"]), stats.sr(h["ew"])]
    got = df.filter(pl.col("statistic") == "dsr").sort("weighting")["estimate"].to_list()
    assert got == pytest.approx([stats.dsr(h["cap"], srs), stats.dsr(h["ew"], srs)])


def test_rerun_is_byte_identical(monkeypatch, tmp_path):
    ret, ff5, ff3, chars = _synth()
    _patch(monkeypatch, ret, ff5, ff3, chars, _expo())
    terciles.run_terciles(tmp_path / "a", fig_dir=tmp_path / "fa")
    terciles.run_terciles(tmp_path / "b", fig_dir=tmp_path / "fb")
    for name in ("terciles.md", "terciles.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
    assert (tmp_path / "fa" / "fig_rq3_tercile_cumulative.png").exists()


def test_no_fig_dir_writes_no_figure(monkeypatch, tmp_path):
    ret, ff5, ff3, chars = _synth()
    _patch(monkeypatch, ret, ff5, ff3, chars, expo=None)
    terciles.run_terciles(tmp_path, expo=_expo(designs=("B",)))
    assert not list(tmp_path.rglob("fig_*"))
