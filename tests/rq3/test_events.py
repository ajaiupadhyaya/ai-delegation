"""D19 event studies and the Eisfeldt, Schubert & Zhang replication (PAP §8.3). Synthetic data
only: weekday calendars, factors N(0, 1) in percent, industries = beta . f + rf + small noise."""

from datetime import date, timedelta

import numpy as np
import polars as pl
import pytest

from aideleg.rq3 import data, events
from aideleg.rq3.events import EVENTS, Event

FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
NAMES = [f"I{i}" for i in range(10)]


def _weekdays(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _synth(start: date = date(2021, 11, 1), n: int = 400, seed: int = 3, noise: float = 1e-4,
           names: list[str] = NAMES) -> tuple[pl.DataFrame, pl.DataFrame]:
    """French-style frames in percent: returns `date, <names>`, factors `date, FACTORS, rf`."""
    rng = np.random.default_rng(seed)
    days = _weekdays(start, n)
    f = rng.standard_normal((n, len(FACTORS)))
    rf = np.full(n, 0.01)
    beta = rng.normal(0.0, 1.0, size=(len(FACTORS), len(names)))
    y = f @ beta + rf[:, None] + noise * rng.standard_normal((n, len(names)))
    factors = pl.DataFrame({"date": days, **{c: f[:, j] for j, c in enumerate(FACTORS)},
                            "rf": rf})
    returns = pl.DataFrame({"date": days, **{nm: y[:, j] for j, nm in enumerate(names)}})
    return returns, factors


def _expo(designs=("A_r2", "A_pooled"), names: list[str] = NAMES, seed: int = 5
          ) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    aioe = rng.standard_normal(len(names))
    rows = []
    for d in designs:
        zd = rng.standard_normal(len(names))
        zu = rng.standard_normal(len(names))
        rows += [{"design": d, "ff49": i + 1, "ff49_short": nm, "z_delegation": float(zd[i]),
                  "z_usage": float(zu[i]), "z_aioe": float(aioe[i])}
                 for i, nm in enumerate(names)]
    return pl.DataFrame(rows)


def _set(returns: pl.DataFrame, col: str, day: date, value) -> pl.DataFrame:
    return returns.with_columns(
        pl.when(pl.col("date") == day).then(value).otherwise(pl.col(col)).alias(col))


def _pos(returns: pl.DataFrame, day: date) -> int:
    return returns["date"].to_list().index(day)


def test_fourteen_events_exact():
    assert [(e.name, e.announced) for e in EVENTS] == [
        ("ChatGPT", date(2022, 11, 30)), ("GPT-4", date(2023, 3, 14)),
        ("PaLM 2", date(2023, 5, 10)), ("Claude 2", date(2023, 7, 11)),
        ("Claude 2.1", date(2023, 11, 21)), ("Gemini 1.0", date(2023, 12, 6)),
        ("Gemini 1.5", date(2024, 2, 15)), ("Claude 3", date(2024, 3, 4)),
        ("Claude 3.5", date(2024, 6, 20)), ("OpenAI o1", date(2024, 9, 12)),
        ("Gemini 2.0", date(2025, 2, 5)), ("Claude 3.7", date(2025, 2, 24)),
        ("GPT-4.5", date(2025, 2, 27)), ("Gemini 2.5", date(2025, 3, 25))]
    assert set(events.EXCLUDED) == {"GPT-4o", "o3-mini", "DeepSeek-R1", "Gemma", "Gemini Ultra"}
    assert events.ESTIMATION == (-250, -21)
    assert events.HORIZONS == (5, 20)
    assert events.ESZ_HORIZON == 9


def test_day_zero_moves_to_next_trading_day():
    days = [d for d in _weekdays(date(2024, 6, 3), 30) if d != date(2024, 6, 20)]
    assert events.day_zero(date(2024, 6, 20), days) == date(2024, 6, 21)
    assert events.day_zero(date(2024, 6, 19), days) == date(2024, 6, 19)
    ed = events.event_days([Event("Claude 3.5", date(2024, 6, 20)),
                            Event("X", date(2024, 6, 10))], days)
    assert ed.columns == ["event", "announced", "day0", "moved", "overlaps"]
    r = ed.row(0, named=True)
    assert r["day0"] == date(2024, 6, 21) and r["moved"] is True
    assert ed.row(1, named=True)["moved"] is False


def test_day_zero_refuses_after_last_day():
    with pytest.raises(ValueError):
        events.day_zero(date(2030, 1, 1), _weekdays(date(2024, 6, 3), 10))


def test_estimation_window_is_250_to_21():
    returns, factors = _synth()
    ev = Event("ChatGPT", date(2022, 11, 30))
    coef, names, n_rows = events.fit_betas(returns, factors, ev.announced)
    assert n_rows == 230 and names == NAMES
    p0 = _pos(returns, ev.announced)
    days = returns["date"].to_list()
    shocked = returns
    for off in (-20, -251):
        d = days[p0 + off]
        shocked = _set(shocked, "I0", d, pl.col("I0") + 5.0)
    coef2, _, _ = events.fit_betas(shocked, factors, ev.announced)
    np.testing.assert_array_equal(coef, coef2)
    # a shock inside the window does move them
    inside = _set(returns, "I0", days[p0 - 21], pl.col("I0") + 5.0)
    coef3, _, _ = events.fit_betas(inside, factors, ev.announced)
    assert not np.array_equal(coef[:, 0], coef3[:, 0])
    inside = _set(returns, "I0", days[p0 - 250], pl.col("I0") + 5.0)
    coef4, _, _ = events.fit_betas(inside, factors, ev.announced)
    assert not np.array_equal(coef[:, 0], coef4[:, 0])


def test_car_recovers_planted_jump():
    returns, factors = _synth()
    ev = Event("ChatGPT", date(2022, 11, 30))
    planted = _set(returns, "I3", ev.announced, pl.col("I3") + 1.0)
    cars = events.event_cars(planted, factors, ev, (5, 20))
    assert cars.columns == ["ff49_short", "car_5", "car_20", "dropped"]
    by = {r["ff49_short"]: r for r in cars.iter_rows(named=True)}
    assert by["I3"]["car_5"] == pytest.approx(0.01, abs=1e-3)
    assert by["I3"]["car_20"] == pytest.approx(0.01, abs=1e-3)
    for nm in NAMES:
        assert by[nm]["dropped"] is None
        if nm != "I3":
            assert by[nm]["car_5"] == pytest.approx(0.0, abs=1e-3)


def test_car_is_sum_of_ar_with_intercept():
    returns, factors = _synth(noise=0.5)
    ev = Event("ChatGPT", date(2022, 11, 30))
    coef, names, _ = events.fit_betas(returns, factors, ev.announced)
    j = returns.join(factors, on="date").sort("date")
    p0 = _pos(j, ev.announced)
    w = j.slice(p0, 6)
    X = np.column_stack([np.ones(6)] + [w[c].to_numpy() / 100 for c in FACTORS])
    y = w["I1"].to_numpy() / 100 - w["rf"].to_numpy() / 100
    expect = float((y - X @ coef[:, 1]).sum())
    cars = events.event_cars(returns, factors, ev, (5,))
    got = cars.filter(pl.col("ff49_short") == "I1")["car_5"][0]
    assert got == pytest.approx(expect, abs=1e-14)


def test_industry_missing_estimation_return_is_dropped():
    returns, factors = _synth()
    ev = Event("ChatGPT", date(2022, 11, 30))
    days = returns["date"].to_list()
    p0 = _pos(returns, ev.announced)
    holed = _set(returns, "I2", days[p0 - 100], None)
    holed = _set(holed, "I4", days[p0 + 12], None)
    cars = events.event_cars(holed, factors, ev, (5, 20))
    by = {r["ff49_short"]: r for r in cars.iter_rows(named=True)}
    assert by["I2"]["car_5"] is None and by["I2"]["dropped"] == "estimation"
    assert by["I4"]["car_5"] is None and by["I4"]["dropped"] == "event"
    car = cars["car_5"].to_numpy().astype(float)
    z = np.arange(len(NAMES), dtype=float)
    r = events.car_regression(car, {"z": z})
    assert r["n"] == 8
    assert set(r["z"]) == {"b", "se", "ci95", "p"}


def test_car_regression_is_hc3_ols():
    import statsmodels.api as sm

    rng = np.random.default_rng(1)
    z = rng.standard_normal(30)
    c = rng.standard_normal(30)
    y = 0.5 * z + rng.standard_normal(30)
    y[4] = np.nan
    r = events.car_regression(y, {"a": z, "c": c})
    ok = ~np.isnan(y)
    fit = sm.OLS(y[ok], sm.add_constant(np.column_stack([z[ok], c[ok]]))).fit(cov_type="HC3")
    assert r["n"] == 29
    assert r["a"]["b"] == pytest.approx(fit.params[1], abs=1e-12)
    assert r["a"]["se"] == pytest.approx(fit.bse[1], abs=1e-12)
    assert r["c"]["p"] == pytest.approx(fit.pvalues[2], abs=1e-12)
    lo, hi = r["a"]["ci95"]
    assert (lo, hi) == pytest.approx(tuple(fit.conf_int()[1]), abs=1e-12)


def test_overlap_flag():
    days = _weekdays(date(2025, 1, 1), 260)
    ed = events.event_days(EVENTS[10:], days)
    by = {r["event"]: r for r in ed.iter_rows(named=True)}
    assert "GPT-4.5" in by["Claude 3.7"]["overlaps"]
    assert "Claude 3.7" not in by["Claude 3.7"]["overlaps"]
    assert by["Gemini 2.5"]["overlaps"] == []


def _patch(monkeypatch, returns, factors, expo, zero=True):
    monkeypatch.setattr(data, "daily", lambda weighting="VW": (returns, factors))
    monkeypatch.setattr(data, "exposures", lambda: expo)
    if zero:
        monkeypatch.setattr(data, "zero_assigned", lambda: pl.DataFrame({
            "design": ["A_pooled", "A_r2", "B"], "occupations": [1, 1, 1],
            "no_usage": [0, 0, 0], "no_usage_emp_pct": [10.0, 12.14, 12.14]}))


def test_esz_runs_aioe_alone_then_with_delegation(monkeypatch, tmp_path):
    returns, factors = _synth(noise=0.5)
    _patch(monkeypatch, returns, factors, _expo())
    df = events.run_events(tmp_path, events=(EVENTS[0],))
    assert df.columns == ["event", "day0", "horizon", "design", "regressors", "regressor", "b",
                          "se", "ci_lo", "ci_hi", "p", "n"]
    esz = df.filter(pl.col("horizon") == 9)
    assert [(r["regressors"], r["design"]) for r in esz.iter_rows(named=True)] == [
        ("z_aioe", None), ("z_aioe+z_delegation", "A_r2"), ("z_aioe+z_delegation", "A_r2"),
        ("z_aioe+z_delegation", "A_pooled"), ("z_aioe+z_delegation", "A_pooled")]
    assert esz["regressor"].to_list() == ["z_aioe", "z_aioe", "z_delegation", "z_aioe",
                                          "z_delegation"]
    main = df.filter(pl.col("horizon") != 9)
    assert [(r["horizon"], r["design"]) for r in main.iter_rows(named=True)] == [
        (5, "A_r2"), (5, "A_pooled"), (20, "A_r2"), (20, "A_pooled")]
    assert set(main["regressors"]) == {"z_delegation"}
    for f in ("event_study.md", "event_study.csv", "event_days.csv", "eisfeldt_replication.md"):
        assert (tmp_path / f).is_file(), f
    md = (tmp_path / "event_study.md").read_text(encoding="utf-8")
    assert md.startswith("# Event studies (exploratory, PAP §8.3 D19)\n")
    assert "chosen with the list in view" in md or "with the source's list in view" in md
    assert "look-ahead" in md
    assert "Zero-assigned employment share, Design A_r2: 12.14% (D3)" in md
    esz_md = (tmp_path / "eisfeldt_replication.md").read_text(encoding="utf-8")
    assert esz_md.startswith("# Eisfeldt, Schubert & Zhang (2023) replication (exploratory)\n")
    from aideleg.results.common import WORDING
    assert md.rstrip().endswith(WORDING) and esz_md.rstrip().endswith(WORDING)
    written = pl.read_csv(tmp_path / "event_study.csv", try_parse_dates=True)
    assert written.height == df.height
    np.testing.assert_array_equal(written["b"].to_numpy(), df["b"].to_numpy())


def test_slopes_are_pp_per_sd(monkeypatch, tmp_path):
    returns, factors = _synth(noise=0.5)
    expo = _expo(designs=("A_r2",))
    _patch(monkeypatch, returns, factors, expo)
    df = events.run_events(tmp_path, events=(Event("Q", date(2022, 11, 30)),), expo=expo)
    cars = events.event_cars(returns, factors, Event("Q", date(2022, 11, 30)), (5, 20))
    z = expo.sort("ff49_short")["z_delegation"].to_numpy()
    car = cars.sort("ff49_short")["car_5"].to_numpy().astype(float)
    r = events.car_regression(car, {"z_delegation": z})
    row = df.filter(pl.col("horizon") == 5).row(0, named=True)
    assert row["b"] == pytest.approx(100 * r["z_delegation"]["b"], abs=1e-12)
    assert row["se"] == pytest.approx(100 * r["z_delegation"]["se"], abs=1e-12)
    assert row["n"] == 10


def test_run_events_takes_expo_and_placebos(monkeypatch, tmp_path):
    returns, factors = _synth(start=date(2018, 3, 1))
    monkeypatch.setattr(data, "daily", lambda weighting="VW": (returns, factors))
    monkeypatch.setattr(data, "exposures", lambda: pytest.fail("exposures() called"))
    monkeypatch.setattr(data, "zero_assigned", lambda: pytest.fail("zero_assigned() called"))
    df = events.run_events(tmp_path, events=(Event("P", date(2019, 3, 14)),),
                           expo=_expo(designs=("A_r2",)))
    assert set(df["design"]) == {"A_r2"}
    assert set(df["event"]) == {"P"}
    assert set(df["horizon"]) == {5, 20}
    assert not (tmp_path / "eisfeldt_replication.md").exists()
    assert (tmp_path / "event_study.csv").is_file()


def test_rerun_is_byte_identical(monkeypatch, tmp_path):
    returns, factors = _synth(noise=0.5)
    _patch(monkeypatch, returns, factors, _expo())
    a, b = tmp_path / "a", tmp_path / "b"
    events.run_events(a, events=(EVENTS[0],), fig_dir=a)
    events.run_events(b, events=(EVENTS[0],), fig_dir=b)
    for f in ("event_study.md", "event_study.csv", "event_days.csv", "eisfeldt_replication.md",
              "fig_rq3_event_slopes.png", "fig_rq3_event_slopes.pdf"):
        assert (a / f).read_bytes() == (b / f).read_bytes(), f
