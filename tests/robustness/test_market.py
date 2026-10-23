"""Market variant runner: guarded loads, recomputed null scales, primary reproduction."""

import importlib
import subprocess
from datetime import date
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from aideleg import confirm_h5, power
from aideleg.config import ROOT
from aideleg.market import french
from aideleg.paper import confirmatory_md
from aideleg.robustness import guards, market, report, returns, upstream

_rq3_guard = importlib.import_module(upstream.assert_confirmatory_recorded.__module__)
FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]


def _boom(*a, **k):
    raise AssertionError("read_french_table was called")


def _refuse(*a, **k):
    raise guards.ProtocolError("market robustness refused: test")


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


# --- protocol order


def test_market_variant_refuses_without_committed_confirmatory(monkeypatch):
    monkeypatch.setattr(guards, "require_confirmatory_committed", _refuse)
    monkeypatch.setattr(french, "read_french_table", _boom)
    with pytest.raises(guards.ProtocolError):
        returns.load_return_set("ff49_vw", date(2026, 8, 31))
    with pytest.raises(guards.ProtocolError):
        returns.load_factors(date(2026, 8, 31))
    expo = pl.DataFrame({"industry": ["A"], "z_delegation": [0.0], "z_aioe": [0.0]})
    with pytest.raises(guards.ProtocolError):
        market.market_variant("R5", "x", expo)


def test_load_return_set_rejects_attempt_only_record(tmp_path, monkeypatch):
    repo = tmp_path
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.org")
    _git(repo, "config", "user.name", "t")
    for rel in guards.H5_FILES:
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_bytes((ROOT / rel).read_bytes())
    md = repo / guards.H5_FILES[0]
    lines = md.read_bytes().split(b"\n")
    lines[0] = b"# Confirmatory test of H5 and H5b: attempt failed"
    md.write_bytes(b"\n".join(lines))
    _git(repo, "add", *guards.H5_FILES)
    _git(repo, "commit", "-q", "-m", "attempt only")
    pinned = {rel: _git(repo, "hash-object", rel) for rel in guards.H5_FILES}
    monkeypatch.setattr(_rq3_guard, "PINNED", pinned)
    monkeypatch.setattr(returns, "ROOT", repo)
    monkeypatch.setattr(french, "read_french_table", _boom)
    with pytest.raises(guards.ProtocolError, match="attempt"):
        returns.load_return_set("ff49_vw", date(2026, 8, 31))


def test_presal_history_needs_no_confirmatory(monkeypatch):
    monkeypatch.setattr(guards, "require_confirmatory_committed", _refuse)
    days = [date(2022, 11, 28), date(2022, 11, 29)]
    stub = pl.DataFrame({"date": days, "A": [0.1, 0.2]})
    monkeypatch.setattr(french, "read_french_table", lambda path, title: stub)
    monkeypatch.setattr(french, "_single_file", lambda key: Path("x.csv"))
    out = returns.load_return_set("ff49_vw", date(2022, 11, 29))
    assert out.columns == ["date", "A"] and out.height == 2
    out = returns.load_return_set("ff30_vw", date(2022, 11, 29))
    assert out.height == 2


def test_load_return_set_drops_rows_after_market_end(monkeypatch):
    monkeypatch.setattr(guards, "require_confirmatory_committed", lambda repo=None: None)
    days = [date(2026, 8, 31), date(2026, 9, 1)]
    stub = pl.DataFrame({"date": days, "A": [0.1, 0.2]})
    monkeypatch.setattr(french, "read_french_table", lambda path, title: stub)
    monkeypatch.setattr(french, "_single_file", lambda key: Path("x.csv"))
    out = returns.load_return_set("ff48_vw", date(2026, 12, 31))
    assert out["date"].to_list() == [date(2026, 8, 31)]


# --- null scales


def _planted_hist(slopes: np.ndarray, n: int = 6) -> tuple[np.ndarray, np.ndarray]:
    """z and a windows x n alpha matrix whose OLS slope on [1, z] is `slopes` exactly."""
    z = np.linspace(-1.0, 1.0, n)
    return z, np.outer(slopes, z) + 0.01


def test_rms_scale():
    z, A = _planted_hist(np.array([1.0, 2.0, 3.0]))
    ns = market.null_scales_for(z, None, A, scale="rms")
    assert ns.bbar == pytest.approx(2.0, abs=1e-12)
    assert ns.s == pytest.approx(np.sqrt(2 / 3), abs=1e-12)
    assert ns.n_windows == 3


def test_nonoverlap_max_scale():
    b = np.random.default_rng(3).normal(size=40)
    z, A = _planted_hist(b)
    ns = market.null_scales_for(z, None, A, scale="nonoverlap_max")
    want = max(float(np.std(b[o::17], ddof=1)) for o in range(17))
    assert ns.s == pytest.approx(want, abs=1e-12)
    assert ns.bbar == pytest.approx(float(np.mean(b)), abs=1e-12)
    cen = np.abs(b - b.mean()) / want
    assert ns.q_0025 == pytest.approx(float(np.quantile(cen, 0.975)), abs=1e-10)
    assert ns.q_005 == pytest.approx(float(np.quantile(cen, 0.95)), abs=1e-10)
    assert ns.crit_0025 == max(power.t_crit(0.025), ns.q_0025)


def test_sd_scale_matches_own_size():
    b = np.random.default_rng(4).normal(size=50)
    z, A = _planted_hist(b)
    ns = market.null_scales_for(z, None, A)
    slopes = power.slope_null_distribution(z, [None] * len(A), alphas=A)
    sz = power.own_size(slopes, {})
    assert ns.s == float(np.std(slopes, ddof=1))
    assert (ns.q_0025, ns.q_005) == (sz["q_0.9875"], sz["q_0.975"])
    assert ns.crit_005 == max(power.t_crit(0.05), sz["q_0.975"])
    with pytest.raises(ValueError, match="scale"):
        market.null_scales_for(z, None, A, scale="mad")


# --- synthetic drop


NAMES5 = ["A", "B", "C", "D", "E"]


def _toy_market(seed: int = 1):
    rng = np.random.default_rng(seed)
    days = pl.date_range(date(1989, 12, 1), date(2026, 9, 30), "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    factors = pl.DataFrame({"date": days, **f, "rf": np.full(n, 0.01)})
    in_win = ((days >= confirm_h5.WINDOW[0]) & (days <= confirm_h5.WINDOW[1])).to_numpy()
    ret = {}
    for j, nm in enumerate(NAMES5):
        ret[nm] = f["mkt_rf"] + 0.01 + rng.normal(0.0, 0.3, n) + np.where(in_win, 0.02 * j, 0)
    r = pl.DataFrame({"date": days, **ret})
    # D has one missing return inside the confirmatory window only
    r = r.with_columns(
        pl.when(pl.col("date") == date(2025, 6, 2)).then(None).otherwise(pl.col("D")).alias("D")
    )
    return r, factors


@pytest.mark.filterwarnings("ignore:divide by zero:RuntimeWarning")  # 3-industry H5b SE
def test_dropped_industry_recomputes_null_scales(monkeypatch):
    r, f = _toy_market()
    monkeypatch.setattr(returns, "load_return_set", lambda rs, end: r.filter(pl.col("date") <= end))
    monkeypatch.setattr(returns, "load_factors", lambda end: f.filter(pl.col("date") <= end))
    expo = pl.DataFrame(
        {
            "industry": NAMES5,
            "z_delegation": [-1.2, -0.4, 0.1, 0.5, 1.0],
            "z_aioe": [0.3, -1.0, 0.8, -0.2, 0.1],
        }
    )
    recs = market.market_variant("R5", "toy", expo, scale="sd")
    assert [x["applies_to"] for x in recs] == ["H5", "H5b"]
    kept = ["A", "B", "C", "E"]
    z = np.array([-1.2, -0.4, 0.1, 1.0])
    c = np.array([0.3, -1.0, 0.8, 0.1])
    A = market.history("ff49_vw", kept)
    assert A.shape == (len(power.historical_windows()), 4)
    alphas = power.window_alphas(r.select("date", *kept), f, *confirm_h5.WINDOW).to_numpy()
    for rec, ctl in zip(recs, (None, c), strict=True):
        assert set(rec) == set(report.ROBUSTNESS_COLUMNS)
        assert rec["n"] == 4 and rec["n_dropped"] == 1 and rec["dropped"] == "D"
        ns = market.null_scales_for(z, ctl, A)
        b = float(power.ols_weights(z, ctl) @ alphas)
        assert rec["estimate"] == pytest.approx(b * 100, abs=1e-12)
        assert rec["scale"] == pytest.approx(ns.s * 100, abs=1e-12)
        assert rec["stat"] == pytest.approx((b - ns.bbar) / ns.s, abs=1e-12)
        assert rec["crit_005"] == ns.crit_005 and rec["crit_0025"] == ns.crit_0025
        assert rec["ci_lo"] == pytest.approx((b - ns.crit_005 * ns.s) * 100, abs=1e-12)
        assert rec["null"] == "b = bbar"
        assert rec["note"].startswith("secondary b = 0: T = ")
    # an industry named in `drop` is removed the same way
    recs = market.market_variant("R7", "toy", expo, drop=("A",))
    assert recs[0]["n"] == 3 and recs[0]["dropped"] == "A, D"


def test_window_slope_exclude(monkeypatch):
    r, f = _toy_market()
    monkeypatch.setattr(returns, "load_return_set", lambda rs, end: r.filter(pl.col("date") <= end))
    monkeypatch.setattr(returns, "load_factors", lambda end: f.filter(pl.col("date") <= end))
    z = np.array([-1.2, -0.4, 0.1, 0.5, 1.0])
    b, dropped = market.window_slope(z, None, "ff49_vw", NAMES5)
    assert dropped == ["D"]
    b2, dropped2 = market.window_slope(
        z, None, "ff49_vw", NAMES5, exclude=lambda d: d == date(2025, 6, 2)
    )
    assert dropped2 == [] and b2 != b


# --- primary reproduction (real data; the confirmatory record is committed)


def _design_b() -> pl.DataFrame:
    return power.load_exposure().rename({"ff49_short": "industry"})


@pytest.mark.data
def test_primary_null_scales_equal_frozen():
    expo = _design_b()
    names = [c for c in power._load_returns()[0].columns if c != "date"]
    by = {r["industry"]: r for r in expo.iter_rows(named=True)}
    z = np.array([by[n]["z_delegation"] for n in names])
    c = np.array([by[n]["z_aioe"] for n in names])
    A = market.history("ff49_vw", names)
    F = confirm_h5.FROZEN
    for ctl, v in ((None, "h5"), (c, "h5b")):
        ns = market.null_scales_for(z, ctl, A)
        assert ns.n_windows == 378
        assert ns.s == pytest.approx(F[f"s_{v}"], abs=1e-12)
        assert ns.bbar == pytest.approx(F[f"bbar_{v}"], abs=1e-12)
        assert ns.q_0025 == pytest.approx(F[f"q_{v}_0.9875"], abs=1e-12)
        assert ns.q_005 == pytest.approx(F[f"q_{v}_0.975"], abs=1e-12)
        assert ns.crit_0025 == pytest.approx(F[f"crit_{v}_0.025"], abs=1e-12)
        assert ns.crit_005 == pytest.approx(F[f"crit_{v}_0.05"], abs=1e-12)


@pytest.mark.data
def test_primary_variant_reproduces_confirmatory():
    rec = confirmatory_md.parse()
    out = market.market_variant("R00", "primary", _design_b())
    for r, hyp in zip(out, ("H5", "H5b"), strict=True):
        row = rec[hyp]
        assert r["applies_to"] == hyp and r["n"] == 49 and r["dropped"] == ""
        assert f"{r['estimate']:.3f}" == row["b"]
        assert f"{r['scale']:.3f}" == row["s"]
        assert f"{r['stat']:.3f}" == row["T_bbar"]
        assert f"{r['p']:.4f}" == row["p_primary"]
        assert f"{r['crit_0025']:.4f}" == row["c_0025"]
        assert f"{r['crit_005']:.4f}" == row["c_005"]
        lo, hi = rec["decision"][hyp]["ci_005"]
        assert (f"{r['ci_lo']:.3f}", f"{r['ci_hi']:.3f}") == (lo, hi)
        assert f"T = {row['T_zero']}" in r["note"]


@pytest.mark.parametrize("col", ["z_delegation", "z_aioe"])
def test_market_variant_refuses_nan_exposure(monkeypatch, col):
    r, f = _toy_market()
    monkeypatch.setattr(returns, "load_return_set", lambda rs, end: r.filter(pl.col("date") <= end))
    monkeypatch.setattr(returns, "load_factors", lambda end: f.filter(pl.col("date") <= end))
    expo = pl.DataFrame(
        {
            "industry": NAMES5,
            "z_delegation": [-1.2, -0.4, 0.1, 0.5, 1.0],
            "z_aioe": [0.3, -1.0, 0.8, -0.2, 0.1],
        }
    ).with_columns(
        pl.when(pl.col("industry") == "B").then(float("nan")).otherwise(pl.col(col)).alias(col)
    )
    with pytest.raises(ValueError, match="NaN"):
        market.market_variant("R5", "toy", expo)
