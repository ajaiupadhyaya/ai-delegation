"""Plan 4 Task 8: the R35 studentised statistic (PAP §8.2 R35), on synthetic inputs."""

from datetime import date

import numpy as np
import polars as pl
import pytest
import statsmodels.api as sm

from aideleg.robustness import studentised

FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
NAMES = ["A", "B", "C"]


def _toy(seed: int = 7, n: int = 300):
    rng = np.random.default_rng(seed)
    days = pl.date_range(date(2000, 1, 3), date(2001, 12, 31), "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)[:n]
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    rf = np.full(n, 0.01)
    factors = pl.DataFrame({"date": days, **f, "rf": rf})
    ret = {
        nm: 0.02 * j + 0.9 * f["mkt_rf"] + 0.3 * f["hml"] + rng.normal(0.0, 0.5 + j, n) + rf
        for j, nm in enumerate(NAMES)
    }
    return pl.DataFrame({"date": days, **ret}), factors


def test_se_sigma_matches_ols_when_independent():
    r, f = _toy()
    start, end = r["date"].min(), r["date"].max()
    X = sm.add_constant(np.column_stack([f[c].to_numpy() / 100 for c in FACTORS]))
    for k, nm in enumerate(NAMES):
        y = r[nm].to_numpy() / 100 - f["rf"].to_numpy() / 100
        want = 252 * sm.OLS(y, X).fit().bse[0]
        omega = np.eye(len(NAMES))[k]
        got = studentised.se_sigma(r, f, start, end, omega, NAMES)
        assert got == pytest.approx(want, rel=1e-8)


def test_se_sigma_window_and_missing():
    r, f = _toy()
    days = r["date"].to_list()
    start, end = days[50], days[200]
    omega = np.array([0.2, -0.5, 0.3])
    sub = r.filter((pl.col("date") >= start) & (pl.col("date") <= end))
    assert studentised.se_sigma(r, f, start, end, omega, NAMES) == pytest.approx(
        studentised.se_sigma(sub, f, start, end, omega, NAMES), rel=1e-12
    )
    bad = r.with_columns(
        pl.when(pl.col("date") == days[100]).then(None).otherwise(pl.col("B")).alias("B")
    )
    with pytest.raises(ValueError, match="missing"):
        studentised.se_sigma(bad, f, start, end, omega, NAMES)


def test_kappa_is_ratio(monkeypatch):
    monkeypatch.setattr(
        studentised,
        "_history_b_se",
        lambda z, control, rs, names: (np.array([1.0, 2.0, 3.0]), np.array([1.0, 1.0, 2.0])),
    )
    assert studentised.kappa(np.zeros(3), None) == 1.0


def test_t_stud():
    assert studentised.t_stud(0.05, 0.01, 2.0, 0.01) == pytest.approx(2.0)
    assert studentised.t_stud(0.0, 0.01, 0.5, 0.04) == pytest.approx(-0.5)
