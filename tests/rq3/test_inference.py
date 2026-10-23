"""Historical-null vector test, influence diagnostics and the parity check (PAP §3.3, P11).

Synthetic data only, except the `data` test, which reads market data through the guarded
loaders.
"""

import numpy as np
import polars as pl
import pytest
import statsmodels.api as sm
from scipy import stats as _st
from statsmodels.stats.outliers_influence import OLSInfluence

from aideleg import power
from aideleg.config import ROOT
from aideleg.rq3 import inference


@pytest.fixture
def synth():
    rng = np.random.default_rng(7)
    n = 10
    names = [f"I{i}" for i in range(n)]
    z = rng.standard_normal(n)
    c = 0.4 * z + rng.standard_normal(n)
    hist = rng.normal(0.0, 0.05, size=(30, n))
    a = rng.normal(0.01, 0.05, size=n)
    return a, z, c, names, hist


def test_vector_test_reproduces_null_scales(synth):
    a, z, c, names, hist = synth
    ns = power.null_scales(hist, z, c, names)
    r = inference.vector_test(a, z, names, hist=hist)
    assert abs(r["s"] - ns["s_h5"]) < 1e-15
    assert abs(r["bbar"] - ns["bbar_h5"]) < 1e-15
    assert r["q_0.975"] == ns["q_h5_0.975"]
    assert r["crit_0.05"] == ns["crit_h5_0.05"]
    rb = inference.vector_test(a, z, names, control=c, hist=hist)
    assert abs(rb["s"] - ns["s_h5b"]) < 1e-15
    assert abs(rb["bbar"] - ns["bbar_h5b"]) < 1e-15
    assert rb["crit_0.05"] == ns["crit_h5b_0.05"]


def test_vector_test_drops_missing_industries(synth):
    a, z, c, names, hist = synth
    a = a.copy()
    a[3] = np.nan
    r = inference.vector_test(a, z, names, control=c, hist=hist)
    assert r["n"] == 9
    assert r["dropped"] == [names[3]]
    keep = np.arange(len(names)) != 3
    ref = inference.vector_test(a[keep], z[keep], [n for n, k in zip(names, keep, strict=True)
                                                   if k], control=c[keep], hist=hist[:, keep])
    assert ref["dropped"] == []
    for k in ("b", "s", "bbar", "q_0.975", "crit_0.05", "T_bbar", "p_bbar", "T_zero", "p_zero",
              "ci_0.05", "n"):
        assert r[k] == ref[k], k


def test_vector_test_reports_both_nulls(synth):
    a, z, c, names, hist = synth
    r = inference.vector_test(a, z, names, control=c, hist=hist)
    assert set(r) == {"b", "s", "bbar", "q_0.975", "crit_0.05", "T_bbar", "p_bbar", "T_zero",
                      "p_zero", "ci_0.05", "n", "dropped"}
    assert r["b"] == pytest.approx(float(power.ols_weights(z, c) @ a), abs=1e-15)
    assert r["T_bbar"] == (r["b"] - r["bbar"]) / r["s"]
    assert r["T_zero"] == r["b"] / r["s"]
    assert r["p_zero"] == 2 * _st.t.sf(abs(r["T_zero"]), 21)
    assert r["p_bbar"] == 2 * _st.t.sf(abs(r["T_bbar"]), 21)
    assert r["crit_0.05"] == max(power.t_crit(0.05), r["q_0.975"])
    lo, hi = r["ci_0.05"]
    assert lo == r["b"] - r["crit_0.05"] * r["s"] and hi == r["b"] + r["crit_0.05"] * r["s"]


def _planted(n=49, seed=11):
    rng = np.random.default_rng(seed)
    names = [f"I{i}" for i in range(n - 1)] + ["Softw"]
    z = rng.standard_normal(n)
    z[-1] = 4.7
    c = 0.5 * z + rng.standard_normal(n)
    a = rng.normal(0.0, 0.03, size=n)
    a[-1] += 0.3
    return a, z, c, names


def test_influence_flags_planted_outlier():
    a, z, c, names = _planted()
    df = inference.influence(a, z, c, names)
    assert df.columns == ["spec", "ff49_short", "dfbetas_b", "cooks_d", "leverage"]
    assert df.height == 2 * len(names)
    h5 = df.filter(df["spec"] == "H5")
    top = h5.sort("cooks_d", descending=True)["ff49_short"][0]
    assert top == "Softw"
    b_all = float(power.ols_weights(z) @ a)
    b_wo = float(power.ols_weights(z[:-1]) @ a[:-1])
    softw = h5.filter(h5["ff49_short"] == "Softw")
    assert np.sign(softw["dfbetas_b"][0]) == np.sign(b_all - b_wo)


def test_influence_matches_statsmodels():
    a, z, c, names = _planted()
    df = inference.influence(a, z, c, names).filter(pl.col("spec") == "H5b")
    ref = OLSInfluence(sm.OLS(a, power._design(z, c)).fit())
    assert df["ff49_short"].to_list() == names
    np.testing.assert_allclose(df["dfbetas_b"].to_numpy(), ref.dfbetas[:, 1], rtol=0, atol=1e-12)
    np.testing.assert_allclose(df["cooks_d"].to_numpy(), ref.cooks_distance[0], rtol=0,
                               atol=1e-12)
    np.testing.assert_allclose(df["leverage"].to_numpy(), ref.hat_matrix_diag, rtol=0,
                               atol=1e-12)


def test_influence_drops_missing_industries():
    a, z, c, names = _planted()
    a = a.copy()
    a[0] = np.nan
    df = inference.influence(a, z, c, names)
    assert names[0] not in df["ff49_short"].to_list()
    assert df.height == 2 * (len(names) - 1)


TEXT = """# Confirmatory test of H5 and H5b

| specification | b | s |
|---|---|---|
| H5 | 1.234 | 2.271 |
| H5b | -0.500 | 2.560 |
| H5 R12 (ranks) | 9.999 | 2.211 |
"""


def test_check_matches_confirmatory_raises_on_mismatch():
    inference.check_matches_confirmatory({"h5": 0.01234, "h5b": -0.005}, TEXT)
    with pytest.raises(ValueError, match="H5"):
        inference.check_matches_confirmatory({"h5": 0.0124, "h5b": -0.005}, TEXT)
    with pytest.raises(ValueError, match="H5b"):
        inference.check_matches_confirmatory({"h5": 0.01234, "h5b": -0.0051}, TEXT)


def test_check_matches_confirmatory_raises_on_missing_row():
    with pytest.raises(ValueError, match="H5b"):
        inference.check_matches_confirmatory({"h5": 0.01234, "h5b": -0.005},
                                             TEXT.replace("| H5b |", "| H5c |"))


def _frames(n_days=5):
    from datetime import date, timedelta

    d = [date(2000, 1, 3) + timedelta(days=i) for i in range(n_days)]
    return (pl.DataFrame({"date": d, "A": [0.0] * n_days}),
            pl.DataFrame({"date": d, "rf": [0.0] * n_days}))


@pytest.fixture
def fake_hist(tmp_path, monkeypatch):
    calls = []
    frames = {"v": _frames()}

    def fake_matrix(windows, returns, factors, names):
        calls.append(list(names))
        return np.arange(len(windows) * len(names), dtype=float).reshape(len(windows), -1)

    monkeypatch.setattr(inference, "DERIVED", tmp_path)
    monkeypatch.setattr(power, "_load_returns", lambda: frames["v"])
    monkeypatch.setattr(power, "_alpha_matrix", fake_matrix)
    return calls, frames, tmp_path


def test_historical_alphas_caches_and_recomputes_on_new_names(fake_hist):
    calls, _, tmp_path = fake_hist
    a1 = inference.historical_alphas(["A", "B"])
    assert a1.shape == (len(power.historical_windows()), 2)
    assert (tmp_path / "rq3/historical_alphas.npz").is_file()
    a2 = inference.historical_alphas(["A", "B"])
    assert len(calls) == 1
    np.testing.assert_array_equal(a1, a2)
    a3 = inference.historical_alphas(["A", "B", "C"])
    assert len(calls) == 2 and a3.shape[1] == 3


def test_historical_alphas_recomputes_when_inputs_change(fake_hist, monkeypatch):
    calls, frames, tmp_path = fake_hist
    inference.historical_alphas(["A", "B"])
    frames["v"] = _frames(6)  # the pre-seal frames changed shape and span
    inference.historical_alphas(["A", "B"])
    assert len(calls) == 2
    inference.historical_alphas(["A", "B"])
    assert len(calls) == 2
    w = power.historical_windows()
    monkeypatch.setattr(power, "historical_windows", lambda: w[:-1])
    assert inference.historical_alphas(["A", "B"]).shape[0] == len(w) - 1
    assert len(calls) == 3
    # a cache written without a fingerprint (or with a stale one) is never served
    np.savez(tmp_path / "rq3/historical_alphas.npz", alphas=np.zeros((1, 2)),
             names=np.array(["A", "B"]))
    assert inference.historical_alphas(["A", "B"]).shape[0] == len(w) - 1
    assert len(calls) == 4


@pytest.mark.parametrize("what", ["alphas", "z", "names", "control", "hist"])
def test_vector_test_rejects_mismatched_lengths(synth, what):
    a, z, c, names, hist = synth
    args = {"alphas": a, "z": z, "names": names, "control": c, "hist": hist}
    args[what] = args[what][:, :-1] if what == "hist" else args[what][:-1]
    with pytest.raises(ValueError, match="lengths differ"):
        inference.vector_test(**args)


@pytest.mark.data
def test_recomputed_b_matches_committed_record():
    alphas, names = inference.confirmatory_alphas()
    assert len(names) == 49 and alphas.shape == (49,)
    b = inference.recomputed_b(alphas, names)
    text = (ROOT / "docs/results/confirmatory_h5.md").read_text(encoding="utf-8")
    inference.check_matches_confirmatory(b, text)
