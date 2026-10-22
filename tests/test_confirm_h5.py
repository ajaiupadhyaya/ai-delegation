"""The confirmatory H5/H5b script, on synthetic data only. The real script is never run here:
the seal is monkeypatched and every loader is replaced by synthetic returns."""

import hashlib
import re
from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg import confirm_h5 as ch
from aideleg import power
from aideleg.config import ROOT
from aideleg.market import seal

FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
NAMES = [f"I{i:02d}" for i in range(1, 50)]
NAMES[33] = "Softw"


def _exposure(seed: int = 9) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    z = rng.normal(size=49)
    z[33] = 5.0
    z = (z - z.mean()) / z.std()
    c = 0.7 * z + rng.normal(size=49)
    c = (c - c.mean()) / c.std()
    return pl.DataFrame({"ff49": list(range(1, 50)), "ff49_short": NAMES,
                         "z_delegation": z, "z_aioe": c})


def _market(start: date, end: date, slope_pp: float = 0.0, softw_only: bool = False,
            seed: int = 1, expo: pl.DataFrame | None = None):
    """Daily synthetic factors and industry returns (percent). Each industry's daily excess
    return carries a planted alpha of slope_pp (pp/yr per 1 SD of z) x z_j, inside [start, end]
    only; with softw_only, only Softw carries it."""
    expo = _exposure() if expo is None else expo
    z = expo["z_delegation"].to_numpy()
    rng = np.random.default_rng(seed)
    days = pl.date_range(start, end, "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    factors = pl.DataFrame({"date": days, **f, "rf": np.full(n, 0.01)}).select(
        "date", "mkt_rf", "smb", "hml", "rmw", "cma", "rf", "umd")
    in_win = ((days >= ch.WINDOW[0]) & (days <= ch.WINDOW[1])).to_numpy()
    ret = {}
    for j, nm in enumerate(NAMES):
        a = slope_pp * z[j] / 252 if (not softw_only or nm == "Softw") else 0.0
        ret[nm] = f["mkt_rf"] + 0.01 + rng.normal(0.0, 0.3, n) + np.where(in_win, a, 0.0)
    return pl.DataFrame({"date": days, **ret}), factors


def _vector_hash(expo: pl.DataFrame) -> str:
    df = expo.select("ff49", "ff49_short", "z_delegation", "z_aioe")
    return hashlib.sha256(df.write_csv(float_precision=10).encode()).hexdigest()


@pytest.fixture
def unsealed(monkeypatch):
    """Synthetic world: pap-v1 'exists', loaders return synthetic data, calls are recorded."""
    calls: list[tuple] = []
    state = {"returns": None, "factors": None}
    expo = _exposure()

    def fake_returns(freq, weighting, end):
        calls.append(("returns", freq, weighting, end))
        return state["returns"].filter(pl.col("date") <= end)

    def fake_factors(freq, end):
        calls.append(("factors", freq, end))
        return state["factors"].filter(pl.col("date") <= end)

    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: True)
    for mod in (ch, power):
        monkeypatch.setattr(mod, "load_industry_returns", fake_returns)
        monkeypatch.setattr(mod, "load_factors", fake_factors)
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    monkeypatch.setattr(ch, "EXPOSURE_SHA256", _vector_hash(expo))
    monkeypatch.setattr(ch, "N_PERM", 199)
    return {"calls": calls, "state": state, "expo": expo}


def test_frozen_constants_equal_power_md():
    text = (ROOT / "docs/pap/power.md").read_text()
    assert ch.FROZEN == power.parse_frozen(text)


def test_exposure_hash_equals_pap():
    text = (ROOT / "docs/pap/pre-analysis-plan.md").read_text()
    assert ch.EXPOSURE_SHA256 in text
    assert re.fullmatch(r"[0-9a-f]{64}", ch.EXPOSURE_SHA256)


def test_refuses_without_pap_tag(monkeypatch, tmp_path):
    monkeypatch.setattr(seal, "pap_frozen", lambda repo=None: False)

    def boom(*a, **k):
        raise AssertionError("a loader was called before the seal check")

    monkeypatch.setattr(ch, "load_industry_returns", boom)
    monkeypatch.setattr(ch, "load_factors", boom)
    with pytest.raises(seal.SealedPeriodError):
        ch.run(out=tmp_path / "c.md")
    assert not (tmp_path / "c.md").exists()


def test_refuses_to_overwrite(unsealed, tmp_path):
    out = tmp_path / "c.md"
    out.write_text("earlier result\n")
    with pytest.raises(FileExistsError):
        ch.run(out=out)
    assert out.read_text() == "earlier result\n"
    assert unsealed["calls"] == []


def test_refuses_on_exposure_hash_mismatch(unsealed, monkeypatch, tmp_path):
    monkeypatch.setattr(ch, "EXPOSURE_SHA256", "0" * 64)
    with pytest.raises(ValueError, match="exposure vector"):
        ch.run(out=tmp_path / "c.md")
    assert not (tmp_path / "c.md").exists()


def test_holm_two_steps():
    assert ch.holm({"H5": 0.01, "H5b": 0.04}) == {"H5": 0.025, "H5b": 0.05}
    assert ch.holm({"H5": 0.03, "H5b": 0.04}) == {"H5": None, "H5b": None}
    assert ch.holm({"H5": 0.20, "H5b": 0.02}) == {"H5": None, "H5b": 0.025}


def test_decide_co_condition_and_wording():
    fz = dict(ch.FROZEN)
    s = fz["s_h5"]
    # H5 far beyond its critical; R13 not; H5b not
    b = {"h5": 10 * s, "h5b": 0.0, "h5_r12": 10 * fz["s_h5_r12"], "h5b_r12": 0.0,
         "h5_r13": 0.0, "h5b_r13": 0.0}
    d = ch.decide(b, fz)
    assert d["primary"]["H5"] == 0.025 and d["primary"]["H5b"] is None
    assert d["co_condition"]["H5"] is False
    assert "driven by Softw" in d["wording"]["H5"]
    b["h5_r13"] = 10 * fz["s_h5_r13"]
    d = ch.decide(b, fz)
    assert d["co_condition"]["H5"] is True
    assert "delegation exposure is priced" in d["wording"]["H5"]
    # rejects but within crit of the frozen historical mean -> fixed P5 wording
    # (an artificial frozen mean, so that the rule is exercised without using the real one)
    fz2 = dict(fz, bbar_h5=10 * s)
    d = ch.decide(dict(b, h5=10.5 * s), fz2)
    assert d["primary"]["H5"] == 0.025
    assert "not distinguishable from the 1990-2022 pattern" in d["wording"]["H5"]
    d = ch.decide({k: 0.0 for k in b}, fz)
    assert d["primary"] == {"H5": None, "H5b": None}
    assert "80% power only against |b| >=" in d["wording"]["H5"]


def test_end_to_end_synthetic_planted_slope(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=40.0)
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "confirmatory_h5.md"
    res = ch.run(out=out)
    # loaders asked only for the confirmatory window's end (no dropped industries)
    assert {c[-1] for c in unsealed["calls"]} == {ch.WINDOW[1]}
    a = power.window_alphas(r, f, *ch.WINDOW).to_numpy()
    z = unsealed["expo"]["z_delegation"].to_numpy()
    assert res["b"]["h5"] == pytest.approx(np.polyfit(z, a, 1)[0])
    assert res["T"]["h5"] == pytest.approx(res["b"]["h5"] / ch.FROZEN["s_h5"])
    assert res["decision"]["primary"]["H5"] == 0.025
    assert res["b"]["h5"] == pytest.approx(0.40, abs=0.05)
    text = out.read_text()
    for needle in ("H5", "H5b", "R12", "R13", "Freedman-Lane", "HC3", "Holm",
                   ch.EXPOSURE_SHA256, "conversations matched to"):
        assert needle in text
    assert set(res["ri"]) == {"h5_exposure", "h5b_exposure", "h5b_freedman_lane"}
    assert all(0 < p <= 1 for p in res["ri"].values())
    with pytest.raises(FileExistsError):
        ch.run(out=out)


def test_end_to_end_synthetic_null_and_softw_only(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=0.0)
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "a.md")
    assert res["decision"]["primary"] == {"H5": None, "H5b": None}
    # a huge alpha at Softw alone: H5 rejects, dropping Softw removes it
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=200.0, softw_only=True,
                   seed=2)
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "b.md")
    assert res["decision"]["primary"]["H5"] is not None
    assert res["decision"]["co_condition"]["H5"] is False
    assert "driven by Softw" in res["decision"]["wording"]["H5"]


def test_dropped_industry_rescales_on_pre_seal_history(unsealed, tmp_path, monkeypatch):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30), slope_pp=0.0)
    r = r.with_columns(pl.when(pl.col("date") == date(2025, 6, 2)).then(None)
                       .otherwise(pl.col("I05")).alias("I05"))
    unsealed["state"].update(returns=r, factors=f)
    res = ch.run(out=tmp_path / "c.md")
    assert res["dropped"] == ["I05"]
    ends = {c[-1] for c in unsealed["calls"]}
    assert ends == {ch.WINDOW[1], power.END}
    # the rescaled values equal what the power module computes on the kept industries
    expo = unsealed["expo"].filter(pl.col("ff49_short") != "I05")
    monkeypatch.setattr(power, "load_exposure", lambda: expo)
    hist = r.drop("I05")
    monkeypatch.setattr(power, "load_industry_returns",
                        lambda fr, w, end: hist.filter(pl.col("date") <= end))
    monkeypatch.setattr(power, "N_PERM", 9)
    pres = power.run_power(out=tmp_path / "p.md")
    want = power.frozen_values(pres)
    for k in ("s_h5", "s_h5b", "bbar_h5", "s_h5_r13", "s_h5b_r12", "crit_h5_0.025"):
        assert res["frozen_used"][k] == pytest.approx(want[k], rel=1e-12)


def test_holm_stops_when_the_first_fails_the_max_critical():
    fz = dict(ch.FROZEN)
    fz["crit_h5_0.025"] = 50.0  # an empirical quantile above t_21 (not the frozen case)
    b = {"h5": 6 * fz["s_h5"], "h5b": 3 * fz["s_h5b"], "h5_r12": 0.0, "h5b_r12": 0.0,
         "h5_r13": 0.0, "h5b_r13": 0.0}
    d = ch.decide(b, fz)
    assert d["holm_level"] == {"H5": 0.025, "H5b": 0.05}
    assert d["primary"] == {"H5": None, "H5b": None}


def test_creates_the_results_directory(unsealed, tmp_path):
    r, f = _market(date(1989, 6, 1), date(2026, 9, 30))
    unsealed["state"].update(returns=r, factors=f)
    out = tmp_path / "docs" / "results" / "confirmatory_h5.md"
    ch.run(out=out)
    assert out.exists()
    assert ch.OUT == ROOT / "docs/results/confirmatory_h5.md"
