"""Plan 4 Task 8: the returns, sample and inference rows R5, R7, R10 (market), R18, R19, R21,
R34 and R35. Stubbed runners (no data) and the null scales against published PAP values."""

import math
from datetime import date

import numpy as np
import polars as pl
import pytest
from scipy import stats

from aideleg import confirm_h5, power
from aideleg.robustness import market, report, returns, rows, studentised
from aideleg.robustness.exposure_variants import OUT_COLUMNS

FACTORS = ["mkt_rf", "smb", "hml", "rmw", "cma", "umd"]
NAMES = [f"I{i:02d}" for i in range(1, 47)] + ["Hardw", "Softw", "Chips"]

EXPECTED = {
    "R5": ({"market"}, "robustness"),
    "R7": ({"market"}, "robustness"),
    "R10": ({"market_lb", "market_ub"}, "robustness"),
    "R18": ({"market"}, "robustness"),
    "R19": ({"market"}, "robustness"),
    "R21": ({"usage", "augmentation"}, "robustness; no error control"),
    "R34": ({"from_1969", "from_1963"}, "robustness"),
}


def _fake_variant(spec):
    assert spec == rows.ExposureSpec()
    n = len(NAMES)
    data = {
        "industry": list(range(1, n + 1)),
        "industry_short": NAMES,
        **{c: [float(k % 7) - 3.0 for k in range(n)] for c in OUT_COLUMNS[2:]},
    }
    return pl.DataFrame(data).select(OUT_COLUMNS)


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: list[dict] = []

    def fake_market(row_id, part, expo, *, label="robustness", **kw):
        assert sorted(expo["industry"].to_list()) == sorted(NAMES)
        calls.append({"row_id": row_id, "part": part, "label": label, **kw})
        out = []
        for hyp in ("H5", "H5b"):
            rec = dict.fromkeys(report.ROBUSTNESS_COLUMNS)
            rec |= {
                "row_id": row_id,
                "part": part,
                "variant": "returns=ff49_vw",
                "applies_to": hyp,
                "label": label,
                "estimand": "slope",
                "unit": report.MARKET_UNIT,
                "estimate": 1.0,
                "scale": 0.5,
                "ci_lo": 0.0,
                "ci_hi": 2.0,
                "stat": 1.0,
                "p": 0.3,
                "null": "b = bbar",
                "crit_0025": 2.4,
                "crit_005": 2.1,
                "n": 49,
                "n_dropped": 0,
                "dropped": "",
                "note": "secondary",
            }
            out.append(rec)
        return out

    monkeypatch.setattr(rows, "variant_exposure", _fake_variant)
    monkeypatch.setattr(rows, "market_variant", fake_market)
    monkeypatch.setattr(rows, "zero_assigned_share", lambda spec: 12.345)
    monkeypatch.setattr(rows, "history_drops", lambda rs, names, first: (3, 2, ["Softw"]))
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    return calls


def _run(row_id):
    # R10's market parts are Task 8's `run_R10_market`; RUNNERS["R10"] (Task 11) carries them
    run = rows.run_R10_market if row_id == "R10" else rows.RUNNERS[row_id]
    csv, md = run()
    return pl.read_csv(csv), md.read_text(encoding="utf-8")


@pytest.mark.parametrize("row_id", sorted(EXPECTED))
def test_market_rows_parts_and_label(stubbed, row_id):
    parts, label = EXPECTED[row_id]
    df, md = _run(row_id)
    assert set(df["part"]) == parts
    assert set(df["label"]) == {label}
    assert set(df["row_id"]) == {row_id}
    assert "Zero-assigned employment share (D3): 12.35%" in md


def test_r21_label_no_error_control(stubbed):
    df, md = _run("R21")
    assert set(df["part"]) == {"usage", "augmentation"}
    assert set(df["label"]) == {"robustness; no error control"}
    assert "no error control" in md
    assert [c["z_col"] for c in stubbed] == ["z_usage", "z_augmentation"]


def test_r7_drops_three(stubbed):
    _, md = _run("R7")
    (call,) = stubbed
    assert call["drop"] == ("Hardw", "Softw", "Chips")
    assert call.get("z_col", "z_delegation") == "z_delegation"
    assert "z not re-standardised" in md
    assert "C-63" in md


def test_market_row_calls(stubbed):
    for rid in ("R5", "R10", "R18", "R19", "R34"):
        _run(rid)
    by = {(c["row_id"], c["part"]): c for c in stubbed}
    assert by[("R5", "market")]["rs"] == "ff49_ew"
    assert by[("R10", "market_lb")]["z_col"] == "z_delegation_lb"
    assert by[("R10", "market_ub")]["z_col"] == "z_delegation_ub"
    assert by[("R18", "market")]["scale"] == "nonoverlap_max"
    assert by[("R19", "market")]["scale"] == "rms"
    assert by[("R34", "from_1969")]["first"] == date(1969, 7, 1)
    assert by[("R34", "from_1963")]["first"] == date(1963, 7, 1)


def test_notes_cite_rules(stubbed):
    _, md18 = _run("R18")
    assert "C-64" in md18
    _, md19 = _run("R19")
    assert "q is recomputed with the RMS s" in md19
    _, md34 = _run("R34")
    assert "1963-07 rows are not like-for-like: industries missing in early windows" in md34
    assert "3 industry-window drops in 2 windows (Softw)" in md34


# --- R35 on a synthetic market


TOY = ["A", "B", "C", "D", "E"]


def _toy_market(seed: int = 2):
    rng = np.random.default_rng(seed)
    days = pl.date_range(date(1989, 12, 1), date(2026, 9, 30), "1d", eager=True)
    days = days.filter(days.dt.weekday() <= 5)
    n = days.len()
    f = {c: rng.normal(0.0, 1.0, n) for c in FACTORS}
    factors = pl.DataFrame({"date": days, **f, "rf": np.full(n, 0.01)})
    ret = {nm: f["mkt_rf"] + 0.01 * j + rng.normal(0.0, 0.3, n) for j, nm in enumerate(TOY)}
    return pl.DataFrame({"date": days, **ret}), factors


def test_r35_records(monkeypatch, tmp_path):
    r, f = _toy_market()
    monkeypatch.setattr(returns, "load_return_set", lambda rs, end: r.filter(pl.col("date") <= end))
    monkeypatch.setattr(returns, "load_factors", lambda end: f.filter(pl.col("date") <= end))
    z = np.array([-1.2, -0.4, 0.1, 0.5, 1.0])
    c = np.array([0.3, -1.0, 0.8, -0.2, 0.1])
    frame = pl.DataFrame(
        {"industry": list(range(1, 6)), "industry_short": TOY}
        | {col: [0.0] * 5 for col in OUT_COLUMNS[2:]}
    ).with_columns(pl.Series("z_delegation", z), pl.Series("z_aioe", c))
    monkeypatch.setattr(rows, "variant_exposure", lambda spec: frame.select(OUT_COLUMNS))
    monkeypatch.setattr(rows, "zero_assigned_share", lambda spec: 12.345)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    df, md = _run("R35")
    assert df["part"].to_list() == ["h5", "h5b"]
    assert df["applies_to"].to_list() == ["H5", "H5b"]
    A = market.history("ff49_vw", TOY)
    alphas = power.window_alphas(r, f, *confirm_h5.WINDOW).to_numpy()
    for rec, ctl in zip(df.iter_rows(named=True), (None, c), strict=True):
        w = power.ols_weights(z, ctl)
        b = float(w @ alphas)
        ns = market.null_scales_for(z, ctl, A)
        k = studentised.kappa(z, ctl, "ff49_vw", names=TOY)
        se = studentised.se_sigma(r, f, *confirm_h5.WINDOW, w, TOY)
        assert rec["estimate"] == pytest.approx(b * 100, abs=1e-12)
        assert rec["scale"] == pytest.approx(k * se * 100, rel=1e-12)
        assert rec["stat"] == pytest.approx((b - ns.bbar) / (k * se), rel=1e-12)
        assert rec["crit_0025"] == power.t_crit(0.025)
        assert rec["crit_005"] == power.t_crit(0.05)
        assert rec["p"] == pytest.approx(2 * stats.t.sf(abs(rec["stat"]), 21), abs=1e-12)
        assert rec["ci_lo"] == pytest.approx((b - power.t_crit(0.05) * k * se) * 100, rel=1e-12)
        assert rec["null"] == "b = bbar"
        assert rec["n"] == 5
    assert "κ" in md and "SE_Σ" in md


# --- null scales against the published PAP values (real pre-seal data)


def _scales(row_id: str, part: str):
    kw = dict(rows.MARKET_ROWS[row_id].parts)[part]
    rs = kw.get("rs", "ff49_vw")
    names = [n for n in returns.load_return_set(rs, power.END).columns if n != "date"]
    expo = power.load_exposure().rename({"ff49_short": "industry"})
    by = {r["industry"]: r for r in expo.iter_rows(named=True)}
    z = np.array([by[n]["z_delegation"] for n in names])
    c = np.array([by[n]["z_aioe"] for n in names])
    A = market.history(rs, names, first=kw.get("first", power.FIRST_START))
    scale = kw.get("scale", "sd")
    return (
        market.null_scales_for(z, None, A, scale=scale),
        market.null_scales_for(z, c, A, scale=scale),
    )


@pytest.mark.data
def test_r18_scales_match_power():
    h5, h5b = _scales("R18", "market")
    assert round(h5.s * 100, 2) == 2.82
    assert round(h5b.s * 100, 2) == 3.22


@pytest.mark.data
def test_r19_scale_exact():
    h5, _ = _scales("R19", "market")
    assert abs(h5.s * 100 - confirm_h5.FROZEN["s_h5"] * math.sqrt(377 / 378) * 100) < 1e-10


@pytest.mark.data
def test_r34_scales_match_power():
    h5_69, h5b_69 = _scales("R34", "from_1969")
    h5_63, h5b_63 = _scales("R34", "from_1963")
    assert (round(h5_69.s * 100, 2), round(h5_63.s * 100, 2)) == (2.51, 2.72)
    assert (round(h5b_69.s * 100, 2), round(h5b_63.s * 100, 2)) == (3.00, 3.53)
    assert (h5_69.n_windows, h5_63.n_windows) == (624, 696)


@pytest.mark.data
def test_kappa_sd_equals_frozen_s():
    names = [n for n in returns.load_return_set("ff49_vw", power.END).columns if n != "date"]
    expo = power.load_exposure().rename({"ff49_short": "industry"})
    by = {r["industry"]: r for r in expo.iter_rows(named=True)}
    z = np.array([by[n]["z_delegation"] for n in names])
    c = np.array([by[n]["z_aioe"] for n in names])
    for ctl, v in ((None, "s_h5"), (c, "s_h5b")):
        b, se = studentised._history_b_se(z, ctl, "ff49_vw", names)
        assert len(b) == len(se) == 378
        assert float(np.std(b, ddof=1)) == confirm_h5.FROZEN[v]
