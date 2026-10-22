"""Pre-seal power analysis for H5/H5b: alpha estimation, MDE formula, windows, and the seal."""

from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg import power
from aideleg.config import SEAL_DATE

NAMES = [f"I{i:02d}" for i in range(1, 50)]
FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]


def _synthetic(start: date, end: date, seed: int = 1) -> tuple[pl.DataFrame, pl.DataFrame]:
    """Daily factors and 49 industry returns in percent, as the French loaders return them."""
    rng = np.random.default_rng(seed)
    days = pl.date_range(start, end, "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    factors = pl.DataFrame({"date": days, **f, "rf": np.full(n, 0.01)}).select(
        "date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf", "umd")
    ret = {nm: f["mkt_rf"] + 0.01 + rng.normal(0.0, 1.0, n) for nm in NAMES}
    return pl.DataFrame({"date": days, **ret}), factors


def test_window_alpha_recovers_planted_alpha():
    rng = np.random.default_rng(7)
    days = pl.date_range(date(2000, 1, 1), date(2009, 12, 31), "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    mkt = rng.normal(0.0, 0.01, n)  # decimal
    factors = pl.DataFrame({"date": days, "mkt_rf": mkt * 100,
                            **{c: rng.normal(0, 0.5, n) for c in FACTORS[1:]},
                            "rf": np.zeros(n)})
    # 1.0 * mkt + 0.0004 per day + noise, in percent
    ret = {nm: (1.0 * mkt + 0.0004 + rng.normal(0, 0.002, n)) * 100 for nm in NAMES}
    returns = pl.DataFrame({"date": days, **ret})
    a = power.window_alphas(returns, factors, date(2000, 1, 1), date(2009, 12, 31))
    assert a.len() == 49
    assert a.null_count() == 0
    assert np.allclose(a.to_numpy(), 0.0004 * 252, atol=0.02)
    assert abs(a.mean() - 0.1008) < 0.02


def test_window_alpha_subtracts_rf_and_drops_missing_industries():
    returns, factors = _synthetic(date(2001, 1, 1), date(2002, 12, 31))
    returns = returns.with_columns(
        pl.when(pl.col("date") == date(2001, 6, 1)).then(None).otherwise(pl.col("I03"))
        .alias("I03"))
    a = power.window_alphas(returns, factors, date(2001, 1, 1), date(2002, 12, 31))
    assert a[2] is None and a.null_count() == 1
    # planted 0.01%/day total return with rf 0.01%/day -> excess alpha about 0
    assert abs(float(np.nanmean(a.to_numpy().astype(float)))) < 0.1


def test_mde_formula():
    rng = np.random.default_rng(3)
    x = rng.normal(size=10_000)
    x = (x - x.mean()) / x.std(ddof=1)
    assert power.mde(x) == pytest.approx(2.241 + 0.8416, abs=1e-3)
    assert power.mde(2 * x) == pytest.approx(2 * (2.2414 + 0.8416), abs=1e-3)


def test_windows_are_17_months_and_end_before_seal():
    w = power.historical_windows()
    assert w[0] == (date(1990, 1, 1), date(1991, 5, 31))
    assert all(e < SEAL_DATE for _, e in w)
    assert w[-1] == (date(2021, 6, 1), date(2022, 10, 31))  # Nov 2022 ends on 11-30
    assert len(w) == 378
    nov = power.non_overlapping(w)
    assert nov[0] == w[0] and nov[1][0] == date(1991, 6, 1)
    assert all(a[1] < b[0] for a, b in zip(nov, nov[1:], strict=False))


def test_slope_with_control_matches_ols():
    returns, factors = _synthetic(date(1995, 1, 1), date(1997, 12, 31))
    rng = np.random.default_rng(5)
    z = rng.normal(size=49)
    c = 0.8 * z + rng.normal(size=49)
    w = [(date(1995, 1, 1), date(1996, 5, 31)), (date(1996, 1, 1), date(1997, 5, 31))]
    s1 = power.slope_null_distribution(z, w, returns=returns, factors=factors)
    s2 = power.slope_null_distribution(z, w, returns=returns, factors=factors, control=c)
    a = power.window_alphas(returns, factors, *w[0]).to_numpy()
    X = np.column_stack([np.ones(49), z, c])
    assert s2[0] == pytest.approx(np.linalg.lstsq(X, a, rcond=None)[0][1])
    assert s1[0] == pytest.approx(np.polyfit(z, a, 1)[0])
    assert s1.shape == s2.shape == (2,)


def test_power_never_reads_sealed_dates(monkeypatch, tmp_path):
    seen: list[date] = []
    returns, factors = _synthetic(date(1989, 6, 1), date(2023, 6, 30))

    def fake_returns(freq, weighting, end):
        seen.append(end)
        return returns.filter(pl.col("date") <= end)

    def fake_factors(freq, end):
        seen.append(end)
        return factors.filter(pl.col("date") <= end)

    rng = np.random.default_rng(9)
    z = rng.normal(size=49)
    expo = pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": NAMES,
                         "z_delegation": z, "z_aioe": 0.7 * z + rng.normal(size=49)})
    monkeypatch.setattr(power, "load_industry_returns", fake_returns)
    monkeypatch.setattr(power, "load_factors", fake_factors)
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    res = power.run_power(out=tmp_path / "power.md", n_perm=19)
    assert res["n_perm"] == 19
    assert seen and all(e < SEAL_DATE for e in seen)
    assert res["max_return_date"] < SEAL_DATE
    text = (tmp_path / "power.md").read_text()
    assert "MDE" in text and "378" in text
    for k in ("mde_h5_overlap", "mde_h5_nonoverlap", "mde_h5b_overlap", "mde_h5b_nonoverlap"):
        assert res[k] > 0


def test_slope_null_distribution_validates_control_length():
    w = [(date(1995, 1, 1), date(1996, 5, 31))]
    with pytest.raises(ValueError, match="control"):
        power.slope_null_distribution(np.zeros(49), w, alphas=np.zeros((1, 49)),
                                      control=np.zeros(48))


@pytest.mark.parametrize(("with_control", "scheme"),
                         [(False, "exposure"), (False, "freedman_lane"), (True, "freedman_lane"),
                          (True, "freedman_lane_coef")])
def test_ri_size_is_nominal_when_industries_are_exchangeable(with_control, scheme):
    rng = np.random.default_rng(11)
    z = rng.normal(size=49)
    c = 0.7 * z + rng.normal(size=49) if with_control else None
    alphas = rng.normal(0.0, 0.05, size=(1000, 49))  # iid across industries: exchangeable
    alphas[0, 4] = np.nan  # a dropped industry is handled
    p = power.ri_pvalues(alphas, z, c, n_perm=999, rng=np.random.default_rng(12),
                         scheme=scheme)
    assert p.shape == (1000,) and ((p > 0) & (p <= 1)).all()
    assert abs(np.mean(p <= 0.05) - 0.05) < 0.02
    assert abs(np.mean(p <= 0.025) - 0.025) < 0.015


def test_ri_permuting_exposure_alone_is_oversized_with_a_collinear_control():
    # documents why H5b also gets the Freedman-Lane row: exchangeable alphas, corr(z, c) ~ 0.5
    rng = np.random.default_rng(11)
    z = rng.normal(size=49)
    c = 0.7 * z + rng.normal(size=49)
    alphas = rng.normal(0.0, 0.05, size=(1000, 49))
    p = power.ri_pvalues(alphas, z, c, n_perm=999, rng=np.random.default_rng(12))
    assert np.mean(p <= 0.05) > 0.065


# --- Task 15b: small-sample criticals, own-size diagnostics, leverage, variants ---------------

def test_t21_criticals_and_mde():
    assert power.T_DF == 21
    assert power.t_crit(0.025) == pytest.approx(2.414, abs=1e-3)
    assert power.t_crit(0.05) == pytest.approx(2.080, abs=1e-3)
    rng = np.random.default_rng(3)
    x = rng.normal(size=5000)
    x = (x - x.mean()) / x.std(ddof=1)
    k = power.t_crit(0.025) + power.t_quantile(0.80)
    assert power.t_quantile(0.80) == pytest.approx(0.859, abs=1e-3)
    assert power.mde_t(3 * x) == pytest.approx(3 * k)


def test_own_size_rates_centred_and_uncentred():
    # slopes = 10 + standard normal; centred rates are about nominal, uncentred are about 1
    rng = np.random.default_rng(4)
    b = 10 + rng.normal(size=200_000)
    o = power.own_size(b, {"n": 1.96})
    assert o["centred_n"] == pytest.approx(0.05, abs=0.003)
    assert o["uncentred_n"] > 0.99
    assert o["excess_kurtosis"] == pytest.approx(0.0, abs=0.05)
    assert o["q_0.9875"] == pytest.approx(2.2414, abs=0.03)
    assert o["q_0.975"] == pytest.approx(1.96, abs=0.02)
    # the 0.9875 symmetrised quantile is the 0.975 quantile of |b - mean| / sd
    s = np.std(b, ddof=1)
    assert o["q_0.9875"] == pytest.approx(np.quantile(np.abs(b - b.mean()) / s, 0.975))


def test_leverage_and_ols_weights():
    rng = np.random.default_rng(6)
    z = rng.normal(size=49)
    z = (z - z.mean()) / z.std()
    c = 0.6 * z + rng.normal(size=49)
    h = power.leverage(z)
    assert h == pytest.approx(1 / 49 + z**2 / 49)  # population-SD z: sum z^2 = 49
    hb = power.leverage(z, c)
    X = np.column_stack([np.ones(49), z, c])
    assert hb == pytest.approx(np.diag(X @ np.linalg.inv(X.T @ X) @ X.T))
    assert hb.sum() == pytest.approx(3.0)
    w = power.ols_weights(z)
    a = rng.normal(size=49)
    assert w @ a == pytest.approx(np.polyfit(z, a, 1)[0])
    wb = power.ols_weights(z, c)
    assert wb @ a == pytest.approx(np.linalg.lstsq(X, a, rcond=None)[0][1])


def test_rank_z_is_population_z_of_average_ranks():
    r = power.rank_z(np.array([3.0, 1.0, 1.0, 10.0]))
    ranks = np.array([3.0, 1.5, 1.5, 4.0])
    assert r == pytest.approx((ranks - ranks.mean()) / ranks.std())


def test_windows_from_1963():
    w = power.historical_windows(date(1963, 7, 1))
    assert w[0] == (date(1963, 7, 1), date(1964, 11, 30))
    assert w[-1][1] <= date(2022, 11, 29)


def test_run_power_reports_t21_size_leverage_variants_and_frozen(monkeypatch, tmp_path):
    returns, factors = _synthetic(date(1963, 7, 1), date(2022, 11, 29))
    rng = np.random.default_rng(9)
    z = rng.normal(size=49)
    z[NAMES.index("I34")] = 5.0
    z = (z - z.mean()) / z.std()
    names = list(NAMES)
    names[33] = "Softw"
    returns = returns.rename({"I34": "Softw"})
    expo = pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": names,
                         "z_delegation": z, "z_aioe": 0.7 * z + rng.normal(size=49)})
    monkeypatch.setattr(power, "load_industry_returns",
                        lambda f, w, end: returns.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "load_factors",
                        lambda f, end: factors.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    monkeypatch.setattr(power, "N_PERM", 99)
    res = power.run_power(out=tmp_path / "power.md")
    assert res["leverage_h5"]["Softw"] == pytest.approx(1 / 49 + z[33] ** 2 / 49)
    assert set(res["leverage_h5b"]) == set(names)
    for hyp in ("h5", "h5b"):
        for var in ("r12", "r13"):
            assert res[f"sd_{hyp}_{var}_overlap"] > 0
        for k in ("centred", "uncentred"):
            for crit in ("n", "t"):
                for lvl in ("0.025", "0.05"):
                    v = res[f"size_{hyp}_overlap"][f"{k}_{crit}_{lvl}"]
                    assert 0.0 <= v <= 1.0
        assert np.isfinite(res[f"bbar_{hyp}"])
        assert res[f"mde_t_{hyp}_overlap"] > res[f"mde_{hyp}_overlap"]
        assert res[f"sd_{hyp}_1963_overlap"] > 0
    text = (tmp_path / "power.md").read_text()
    assert "t_21" in text and "Frozen values" in text and "Softw" in text
    frozen = power.parse_frozen(text)
    assert frozen["bbar_h5"] == res["bbar_h5"]
    assert frozen["s_h5"] == res["sd_h5_overlap"]
    assert frozen["s_h5b_r13"] == res["sd_h5b_r13_overlap"]
    for v in ("h5_r12", "h5b_r12", "h5_r13", "h5b_r13"):
        assert frozen[f"bbar_{v}"] == res[f"bbar_{v}"]
    o = res["size_h5_nonoverlap"]
    assert {"centred_frozen_t_0.025", "centred_frozen_n_0.05"} <= set(o)
    assert "centred on the frozen" in text


def test_own_size_centred_on_a_given_mean():
    rng = np.random.default_rng(4)
    b = 10 + rng.normal(size=100_000)
    o = power.own_size(b, {"n": 1.96}, center=11.0)  # one sd off: |N(-1,1)| > 1.96
    expect = 1 - (_norm_cdf(2.96) - _norm_cdf(-0.96))
    assert o["centred_frozen_n"] == pytest.approx(expect, abs=0.005)
    assert o["centred_n"] == pytest.approx(0.05, abs=0.003)
    assert "centred_frozen_n" not in power.own_size(b, {"n": 1.96})


def _norm_cdf(x):
    from statistics import NormalDist
    return NormalDist().cdf(x)


# --- K4: Freedman-Lane with the pivotal t (Winkler et al. 2014) --------------------------------

def _fl_reference(a, z, c, n_perm, seed, stat):
    """Brute force: y* = H0 y + P e, refit [1, c, z] per draw; |t| or |coef| of z."""
    ok = ~np.isnan(a)
    y, zz, cc = a[ok], z[ok], c[ok]
    X0 = np.column_stack([np.ones(len(y)), cc])
    X = np.column_stack([X0, zz])
    fit0 = X0 @ np.linalg.lstsq(X0, y, rcond=None)[0]
    e = y - fit0
    draws = np.random.default_rng(seed).permuted(np.tile(e, (n_perm, 1)), axis=1)

    def score(yy):
        coef = np.linalg.lstsq(X, yy, rcond=None)[0]
        if stat == "coef":
            return coef[2]
        r = yy - X @ coef
        s2 = r @ r / (len(yy) - X.shape[1])
        return coef[2] / np.sqrt(s2 * np.linalg.inv(X.T @ X)[2, 2])

    obs = score(y)
    perm = np.array([score(fit0 + d) for d in draws])
    return (1 + np.sum(np.abs(perm) >= np.abs(obs) * (1 - 1e-12))) / (n_perm + 1), obs


@pytest.mark.parametrize(("scheme", "stat"),
                         [("freedman_lane", "t"), ("freedman_lane_coef", "coef")])
def test_freedman_lane_statistic_matches_brute_force(scheme, stat):
    rng = np.random.default_rng(21)
    z = rng.normal(size=49)
    c = 0.7 * z + rng.normal(size=49)
    alphas = rng.normal(0.0, 0.05, size=(6, 49)) + 0.01 * z  # a little signal
    alphas[2, 7] = np.nan
    for i, a in enumerate(alphas):
        p = power.ri_pvalues(a[None, :], z, c, n_perm=199, rng=np.random.default_rng(100 + i),
                             scheme=scheme)[0]
        want, obs = _fl_reference(a, z, c, 199, 100 + i, stat)
        assert p == pytest.approx(want)
    # the observed FL t is the conventional OLS t of the coefficient on z
    _, t_obs = _fl_reference(alphas[0], z, c, 1, 0, "t")
    b, se, _ = power._cross_section(alphas[0], z, c)
    assert t_obs == pytest.approx(b / se)


def test_freedman_lane_t_and_coef_differ_but_share_draws(monkeypatch, tmp_path):
    returns, factors = _synthetic(date(1989, 6, 1), date(2022, 11, 29), seed=3)
    rng = np.random.default_rng(9)
    z = rng.normal(size=49)
    expo = pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": NAMES,
                         "z_delegation": z, "z_aioe": 0.7 * z + rng.normal(size=49)})
    monkeypatch.setattr(power, "load_industry_returns",
                        lambda f, w, end: returns.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "load_factors",
                        lambda f, end: factors.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    res = power.run_power(out=tmp_path / "power.md", n_perm=49)
    for lvl in (0.025, 0.05):
        for sch in ("overlap", "nonoverlap"):
            assert 0 <= res[f"ri_reject_h5b_fl_{sch}_{lvl}"] <= 1
            assert 0 <= res[f"ri_reject_h5b_flc_{sch}_{lvl}"] <= 1
    text = (tmp_path / "power.md").read_text()
    assert "Freedman-Lane, pivotal t" in text and "Freedman-Lane, coefficient" in text


def test_main_refuses_once_the_pap_is_frozen(monkeypatch):
    from aideleg.market import seal

    def boom(*a, **k):
        raise AssertionError("run_power was called after the tag")

    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    monkeypatch.setattr(power, "run_power", boom)
    with pytest.raises(SystemExit, match="pap-v1"):
        power.main()
