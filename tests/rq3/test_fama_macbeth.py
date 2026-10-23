"""Fama-MacBeth (PAP §8.3, exploratory; §11 C-35, C-38). Synthetic data only: French-style
frames in percent, month-end calendars."""

import calendar
import math
from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg.results.common import WORDING, check_text
from aideleg.rq3 import data, fama_macbeth, stats, terciles

NAMES = [f"I{i:02d}" for i in range(12)]


def _month_ends(start: date, end: date) -> list[date]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(date(y, m, calendar.monthrange(y, m)[1]))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _expo(designs=("B", "A_r2", "A_pooled"), seed: int = 5, names=NAMES) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for d in designs:
        z = rng.standard_normal(len(names))
        rows += [{"design": d, "ff49": i + 1, "ff49_short": nm, "z_delegation": float(z[i]),
                  "z_usage": 0.0, "z_aioe": 0.0} for i, nm in enumerate(names)]
    return pl.DataFrame(rows, schema={"design": pl.String, "ff49": pl.Int64,
                                      "ff49_short": pl.String, "z_delegation": pl.Float64,
                                      "z_usage": pl.Float64, "z_aioe": pl.Float64})


def _chars(rows: list[tuple[date, str, float]]) -> pl.DataFrame:
    """`date, me_date, ff49_short, n_firms, avg_size, cap`, me_date as `data` sets it."""
    df = pl.DataFrame(rows, schema={"date": pl.Date, "ff49_short": pl.String,
                                    "avg_size": pl.Float64}, orient="row")
    return df.with_columns(me_date=data.me_date_expr("date"), n_firms=pl.lit(10.0),
                           cap=pl.col("avg_size") * 10.0).select(
        "date", "me_date", "ff49_short", "n_firms", "avg_size", "cap")


def _beme(rows: list[tuple[int, str, float | None]]) -> pl.DataFrame:
    return pl.DataFrame(rows, schema={"year": pl.Int64, "ff49_short": pl.String,
                                      "beme": pl.Float64}, orient="row")


def _synth(seed: int = 3, start=date(2021, 1, 31), end=date(2026, 8, 31), names=NAMES):
    rng = np.random.default_rng(seed)
    months = _month_ends(start, end)
    n = len(months)
    y = rng.normal(0.8, 4.0, size=(n, len(names)))
    ret = pl.DataFrame({"date": months, **{nm: y[:, j] for j, nm in enumerate(names)}})
    ff = pl.DataFrame({"date": months, "mkt_rf": rng.standard_normal(n), "smb": 0.0,
                       "hml": 0.0, "rmw": 0.0, "cma": 0.0, "rf": np.full(n, 0.25), "umd": 0.0})
    sizes = rng.uniform(100.0, 5000.0, size=(n, len(names)))
    chars = _chars([(m, nm, float(sizes[i, j])) for i, m in enumerate(months)
                    for j, nm in enumerate(names)])
    years = range(start.year - 1, end.year + 1)
    be = _beme([(yr, nm, float(rng.uniform(0.2, 1.5))) for yr in years for nm in names])
    return ret, ff, chars, be


def _patch(monkeypatch, ret, ff, chars, be, expo=None):
    monkeypatch.setattr(data, "monthly", lambda weighting="VW": (ret, ff))
    monkeypatch.setattr(data, "characteristics", lambda: chars)
    monkeypatch.setattr(data, "beme", lambda: be)
    if expo is None:
        monkeypatch.setattr(data, "exposures", lambda: pytest.fail("exposures() called"))
        monkeypatch.setattr(data, "zero_assigned",
                            lambda: pytest.fail("zero_assigned() called"))
    else:
        monkeypatch.setattr(data, "exposures", lambda: expo)
        monkeypatch.setattr(data, "zero_assigned", lambda: pl.DataFrame({
            "design": ["A_pooled", "A_r2", "B"], "occupations": [1, 1, 1],
            "no_usage": [0, 0, 0], "no_usage_emp_pct": [10.0, 12.0, 12.5]}))


# --- characteristics -------------------------------------------------------------------


def _mom_ret(plant: int | None) -> pl.DataFrame:
    months = _month_ends(date(2023, 1, 31), date(2024, 1, 31))  # 13 months; t = 2024-01-31
    r = [1.0] * len(months)
    if plant is not None:
        r[len(months) - 1 - plant] = 50.0
    return pl.DataFrame({"date": months, "I00": r})


def _mom_at(df: pl.DataFrame, t: date) -> float | None:
    return df.filter((pl.col("date") == t) & (pl.col("ff49_short") == "I00"))["mom"][0]


def test_momentum_skips_most_recent_month():
    t = date(2024, 1, 31)
    base = fama_macbeth.momentum_12_2(_mom_ret(None))
    assert base.columns == ["date", "ff49_short", "mom"]
    assert _mom_at(base, t) == pytest.approx(1.01 ** 11 - 1)
    assert _mom_at(fama_macbeth.momentum_12_2(_mom_ret(1)), t) == pytest.approx(
        _mom_at(base, t))
    assert _mom_at(fama_macbeth.momentum_12_2(_mom_ret(2)), t) == pytest.approx(
        1.01 ** 10 * 1.5 - 1)
    # t - 12 is in the window, t - 13 is not
    assert _mom_at(fama_macbeth.momentum_12_2(_mom_ret(12)), t) == pytest.approx(
        1.01 ** 10 * 1.5 - 1)


def test_momentum_null_unless_all_eleven_present():
    df = _mom_ret(None).with_columns(
        pl.when(pl.col("date") == date(2023, 6, 30)).then(None).otherwise(pl.col("I00"))
        .alias("I00"))
    out = fama_macbeth.momentum_12_2(df)
    assert _mom_at(out, date(2024, 1, 31)) is None
    # a month absent from the frame also nulls it
    short = _mom_ret(None).filter(pl.col("date") != date(2023, 3, 31))
    assert _mom_at(fama_macbeth.momentum_12_2(short), date(2024, 1, 31)) is None
    # fewer than 12 prior months
    assert _mom_at(out, date(2023, 12, 31)) is None


def test_beme_year_assignment():
    assert fama_macbeth.beme_year(date(2023, 6, 30)) == 2022
    assert fama_macbeth.beme_year(date(2023, 7, 31)) == 2023
    assert fama_macbeth.beme_year(date(2023, 12, 31)) == 2023
    assert fama_macbeth.beme_year(date(2024, 1, 31)) == 2023


def test_july_boundary_through_fm_panel(monkeypatch):
    ret, ff, chars, _ = _synth()
    be = _beme([(yr, nm, 0.4 if yr == 2022 else (0.9 if yr == 2023 else 1.2))
                for yr in range(2020, 2027) for nm in NAMES])
    _patch(monkeypatch, ret, ff, chars, be)
    p = fama_macbeth.fm_panel(_expo(designs=("A_r2",)),
                              [date(2023, 6, 30), date(2023, 7, 31)])
    row = p.filter(pl.col("ff49_short") == "I03").sort("date")
    assert row["log_beme"].to_list() == pytest.approx([math.log(0.4), math.log(0.9)])


@pytest.mark.parametrize("offset,row_date", [(1, date(2024, 2, 29)), (0, date(2024, 1, 31))])
def test_size_uses_prior_month_end_me(monkeypatch, offset, row_date):
    monkeypatch.setattr(data, "SIZE_ME_OFFSET", offset)
    ret, ff, _, be = _synth()
    chars = _chars([(date(2024, 1, 31), nm, 100.0) for nm in NAMES]
                   + [(date(2024, 2, 29), nm, 400.0) for nm in NAMES])
    _patch(monkeypatch, ret, ff, chars, be)
    p = fama_macbeth.fm_panel(_expo(designs=("B",)), [date(2024, 2, 29)])
    expected = {date(2024, 2, 29): math.log(400.0), date(2024, 1, 31): math.log(100.0)}
    assert p.columns == ["date", "ff49_short", "ret_x", "z", "log_size", "log_beme", "mom"]
    assert p["log_size"].to_list() == pytest.approx([expected[row_date]] * len(NAMES))


def test_fm_panel_values(monkeypatch):
    ret, ff, chars, be = _synth()
    _patch(monkeypatch, ret, ff, chars, be)
    expo = _expo(designs=("B",))
    t = date(2025, 8, 31)
    p = fama_macbeth.fm_panel(expo, [t])
    r = p.filter(pl.col("ff49_short") == "I05")
    assert r["ret_x"][0] == pytest.approx(
        ret.filter(pl.col("date") == t)["I05"][0] - 0.25)
    assert r["z"][0] == expo.filter(pl.col("ff49_short") == "I05")["z_delegation"][0]
    b = be.filter((pl.col("year") == 2025) & (pl.col("ff49_short") == "I05"))["beme"][0]
    assert r["log_beme"][0] == pytest.approx(math.log(b))
    mom = fama_macbeth.momentum_12_2(ret)
    m = mom.filter((pl.col("date") == t) & (pl.col("ff49_short") == "I05"))["mom"][0]
    assert r["mom"][0] == pytest.approx(m)


def test_nonpositive_or_missing_characteristics_are_null(monkeypatch):
    ret, ff, chars, be = _synth()
    t = date(2025, 8, 31)
    chars = chars.with_columns(
        pl.when((pl.col("ff49_short") == "I01") & (pl.col("me_date") == date(2025, 7, 31)))
        .then(0.0).otherwise(pl.col("avg_size")).alias("avg_size"))
    be = be.with_columns(
        pl.when((pl.col("ff49_short") == "I02") & (pl.col("year") == 2025)).then(None)
        .otherwise(pl.col("beme")).alias("beme"))
    _patch(monkeypatch, ret, ff, chars, be)
    p = fama_macbeth.fm_panel(_expo(designs=("B",)), [t])
    assert p.filter(pl.col("ff49_short") == "I01")["log_size"][0] is None
    assert p.filter(pl.col("ff49_short") == "I02")["log_beme"][0] is None


def test_fm_panel_refuses_month_without_returns_or_rf(monkeypatch):
    ret, ff, chars, be = _synth(end=date(2025, 12, 31))
    _patch(monkeypatch, ret, ff, chars, be)
    with pytest.raises(ValueError, match="returns"):
        fama_macbeth.fm_panel(_expo(designs=("B",)), [date(2026, 1, 31)])
    ff2 = ff.with_columns(pl.when(pl.col("date") == date(2025, 5, 31)).then(None)
                          .otherwise(pl.col("rf")).alias("rf"))
    _patch(monkeypatch, ret, ff2, chars, be)
    with pytest.raises(ValueError, match="rf"):
        fama_macbeth.fm_panel(_expo(designs=("B",)), [date(2025, 5, 31)])


# --- estimation ------------------------------------------------------------------------


def _panel(n_months=120, n_ind=49, slope=0.5, noise=1.0, seed=11) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    months = _month_ends(date(2010, 1, 31), date(2030, 12, 31))[:n_months]
    z = rng.standard_normal(n_ind)
    rows = []
    for t in months:
        ls = rng.normal(7.0, 1.0, n_ind)
        lb = rng.normal(-0.5, 0.4, n_ind)
        mo = rng.normal(0.1, 0.2, n_ind)
        y = 0.3 + slope * z + noise * rng.standard_normal(n_ind)
        rows += [{"date": t, "ff49_short": f"I{j:02d}", "ret_x": float(y[j]), "z": float(z[j]),
                  "log_size": float(ls[j]), "log_beme": float(lb[j]), "mom": float(mo[j])}
                 for j in range(n_ind)]
    return pl.DataFrame(rows)


def _monthly_ols(panel: pl.DataFrame, regs: list[str]) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {r: [] for r in regs}
    for (_t,), g in panel.sort("date").group_by(["date"], maintain_order=True):
        g = g.drop_nulls(["ret_x", *regs])
        if g.height <= len(regs) + 1:
            continue
        X = np.column_stack([np.ones(g.height), g.select(regs).to_numpy()])
        b = np.linalg.lstsq(X, g["ret_x"].to_numpy(), rcond=None)[0]
        for i, r in enumerate(regs):
            out[r].append(float(b[i + 1]))
    return out


def test_fm_recovers_planted_slope():
    res = fama_macbeth.fama_macbeth(_panel())
    assert set(res) == {"z", "log_size", "log_beme", "mom"}
    assert res["z"]["mean"] == pytest.approx(0.5, abs=0.05)
    assert res["z"]["T"] == 120
    assert res["z"]["skipped"] == 0
    assert res["z"]["n_mean"] == pytest.approx(49.0)


def test_fm_se_is_nw_of_monthly_coefficients():
    panel = _panel(n_months=60, seed=4)
    res = fama_macbeth.fama_macbeth(panel)
    coefs = _monthly_ols(panel, ["z", "log_size", "log_beme", "mom"])
    for r, series in coefs.items():
        h = stats.hac_regression(np.asarray(series), None)
        assert res[r]["mean"] == pytest.approx(float(np.mean(series)))
        assert res[r]["se"] == pytest.approx(float(h["se"][0]))
        assert res[r]["p"] == pytest.approx(float(h["p"][0]))
        lo, hi = res[r]["ci95"]
        tc = __import__("scipy").stats.t.ppf(0.975, 60 - 1)
        assert lo == pytest.approx(res[r]["mean"] - tc * res[r]["se"])
        assert hi == pytest.approx(res[r]["mean"] + tc * res[r]["se"])


def test_month_with_too_few_complete_industries_is_skipped_and_counted():
    panel = _panel(n_months=30, n_ind=10)
    first = panel["date"].min()
    keep = ["I00", "I01", "I02", "I03", "I04"]  # n = 5 = len(regressors) + 1 -> skipped
    panel = panel.with_columns(
        pl.when((pl.col("date") == first) & ~pl.col("ff49_short").is_in(keep)).then(None)
        .otherwise(pl.col("mom")).alias("mom"))
    res = fama_macbeth.fama_macbeth(panel)
    assert res["z"]["skipped"] == 1
    assert res["z"]["T"] == 29
    assert fama_macbeth.skipped_months(panel) == [first]
    # with two regressors, n = 5 > 3 complete industries is enough
    assert fama_macbeth.fama_macbeth(panel, ("z", "log_size"))["z"]["skipped"] == 0


def test_fm_refuses_when_too_few_months_remain():
    panel = _panel(n_months=3, n_ind=10)
    panel = panel.with_columns(pl.when(pl.col("date") != panel["date"].min()).then(None)
                               .otherwise(pl.col("ret_x")).alias("ret_x"))
    with pytest.raises(ValueError, match="month"):
        fama_macbeth.fama_macbeth(panel)


def test_fm_refuses_rank_deficient_month():
    panel = _panel(n_months=12, n_ind=20).with_columns(log_beme=pl.col("z") * 2.0)
    with pytest.raises(ValueError, match="rank"):
        fama_macbeth.fama_macbeth(panel)


# --- run -------------------------------------------------------------------------------


def test_run_fm_months_and_expo(monkeypatch, tmp_path):
    ret, ff, chars, be = _synth()
    ms = [m for m in terciles.window_months("A") if m.year != 2024]
    bad = ms[3]
    # only 3 industries keep a size in `bad` (a return gap would also null 11 months of mom)
    chars = chars.with_columns(
        pl.when((pl.col("me_date") == terciles._prior_month_end(bad))
                & pl.col("ff49_short").is_in(NAMES[3:])).then(None)
        .otherwise(pl.col("avg_size")).alias("avg_size"))
    _patch(monkeypatch, ret, ff, chars, be, expo=None)
    seen: list = []
    real = fama_macbeth.fm_panel

    def spy(expo, months):
        seen.append(list(months))
        return real(expo, months)

    monkeypatch.setattr(fama_macbeth, "fm_panel", spy)
    df = fama_macbeth.run_fm(tmp_path, months={"A": ms}, expo=_expo(designs=("A_r2",)))
    assert df.columns == ["design", "window", "regressor", "mean", "se", "ci_lo", "ci_hi", "p",
                          "T", "n_mean", "skipped"]
    assert set(df["design"]) == {"A_r2"}
    assert set(df["window"]) == {"A"}
    assert seen == [ms]
    assert set(df["T"]) == {len(ms) - 1}
    assert set(df["skipped"]) == {1}
    md = (tmp_path / "fama_macbeth.md").read_text(encoding="utf-8")
    assert f"{bad:%Y-%m}" in md


def test_run_fm_default_designs_doc_and_csv(monkeypatch, tmp_path):
    ret, ff, chars, be = _synth()
    expo = _expo()
    expo = expo.with_columns(pl.when((pl.col("design") == "B") & (pl.col("ff49_short") == "I07"))
                             .then(None).otherwise(pl.col("z_delegation")).alias("z_delegation"))
    _patch(monkeypatch, ret, ff, chars, be, expo=expo)
    df = fama_macbeth.run_fm(tmp_path)
    assert df.select("design", "window").unique(maintain_order=True).rows() == [
        ("B", "B"), ("A_r2", "A"), ("A_pooled", "A")]
    assert df.filter(pl.col("design") == "B")["T"][0] == len(terciles.window_months("B"))
    md = (tmp_path / "fama_macbeth.md").read_text(encoding="utf-8")
    assert md.startswith("# Fama–MacBeth (exploratory, PAP §8.3)")
    assert "look-ahead" in md
    for pct in ("12.50% (D3)", "12.00% (D3)", "10.00% (D3)"):
        assert pct in md
    assert "I07" in md  # null exposure listed
    z = df.filter((pl.col("design") == "B") & (pl.col("regressor") == "z"))
    assert f"{12 * z['mean'][0]:.3f}" in md  # x 12 shown
    csv = pl.read_csv(tmp_path / "fama_macbeth.csv")
    assert csv.height == df.height == 12
    check_text(md)  # no stars, no forbidden phrase
    assert md.count(WORDING) == 1


def test_run_fm_refuses_months_outside_window(monkeypatch, tmp_path):
    ret, ff, chars, be = _synth()
    _patch(monkeypatch, ret, ff, chars, be, expo=None)
    with pytest.raises(ValueError, match="outside"):
        fama_macbeth.run_fm(tmp_path, months={"B": [date(2025, 3, 31)]},
                            expo=_expo(designs=("B",)))


def test_run_fm_rerun_is_byte_identical(monkeypatch, tmp_path):
    ret, ff, chars, be = _synth()
    _patch(monkeypatch, ret, ff, chars, be, expo=_expo())
    fama_macbeth.run_fm(tmp_path / "a")
    fama_macbeth.run_fm(tmp_path / "b")
    for name in ("fama_macbeth.md", "fama_macbeth.csv"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()


def test_main_has_fm_subcommand(monkeypatch):
    from aideleg.rq3 import __main__ as cli

    called = {}

    def fake(out_dir, months=None, expo=None):
        called["out"] = out_dir
        return pl.DataFrame({"design": ["B"], "window": ["B"], "regressor": ["z"],
                             "mean": [0.1], "se": [0.2], "ci_lo": [-0.3], "ci_hi": [0.5],
                             "p": [0.6], "T": [17], "n_mean": [49.0], "skipped": [0]})

    monkeypatch.setattr(fama_macbeth, "run_fm", fake)
    assert cli.main(["fm"]) == 0
    assert called["out"] == cli.OUT_DIR
