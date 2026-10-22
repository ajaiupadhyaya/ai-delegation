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
    res = power.run_power(out=tmp_path / "power.md")
    assert seen and all(e < SEAL_DATE for e in seen)
    assert res["max_return_date"] < SEAL_DATE
    text = (tmp_path / "power.md").read_text()
    assert "MDE" in text and "378" in text
    for k in ("mde_h5_overlap", "mde_h5_nonoverlap", "mde_h5b_overlap", "mde_h5b_nonoverlap"):
        assert res[k] > 0
