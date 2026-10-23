"""Plan 4 Task 13: the H4 rows R28 (through Plan 2's `build_geo_sample` and `estimate_h4`, and
Plan 4's own r4/r5 frame `h4_frame_r45`, PAP §11 C-59) and the split family R25 (Plan 2's
`holm` on the committed primary p-values)."""

import math
from datetime import date

import numpy as np
import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.robustness import guards, rows, upstream
from aideleg.robustness import rq1 as RQ
from aideleg.robustness.upstream import Coef, HypothesisResult

P4 = date(2025, 11, 13)
TASK13_RUNNERS = ("R25", "R28")
SCHEMA = {
    c: (
        pl.Date
        if c.startswith("period")
        else pl.Int64
        if c == "level"
        else pl.Float64
        if c == "value"
        else pl.String
    )
    for c in PANEL_COLUMNS
}


def _rows(release, geo_level, geo_id, taxonomy, node_id, metrics, period=P4):
    return [
        (
            release,
            period,
            period,
            "claude_ai",
            geo_level,
            geo_id,
            taxonomy,
            0,
            node_id,
            f"task {node_id}" if taxonomy == "onet_task" else node_id,
            m,
            None if v is None else float(v),
            "collab_v2",
        )
        for m, v in metrics.items()
    ]


# Global task usage and automation: task 1 -> G1, task 2 -> G1 and G2 (split equally),
# task 3 -> G2, task 4 has no GWA, task 5 -> G2 with no published automation, task 6 -> G3,
# whose only task has no automation (so G3 has no a_bar).
GLOBAL_TASKS = {
    "1": {"pct": 2, "automation_pct": 40},
    "2": {"pct": 2, "automation_pct": 60},
    "3": {"pct": 1, "automation_pct": 20},
    "4": {"pct": 5, "automation_pct": 90},
    "5": {"pct": 3, "automation_pct": None},
    "6": {"pct": 1, "automation_pct": None},
}
GWA = pl.DataFrame(
    {"task_id": [1, 2, 2, 3, 5, 6], "family": ["G1", "G1", "G2", "G2", "G2", "G3"]},
    schema={"task_id": pl.Int64, "family": pl.String},
)
A_G1, A_G2 = (2 * 40 + 1 * 60) / 3, (1 * 60 + 1 * 20) / 2  # task 2 counts 1/2 in each


def _panel(countries, release="r4"):
    """countries: {iso: (automation_pct, usage_pct, {task: pct})}."""
    recs = []
    for nid, ms in GLOBAL_TASKS.items():
        recs += _rows(release, "global", "GLOBAL", "onet_task", nid, ms)
    recs += _rows(release, "global", "GLOBAL", "overall", "overall", {"automation_pct": 45})
    for iso, (a, u, tasks) in countries.items():
        recs += _rows(
            release, "country", iso, "overall", "overall", {"automation_pct": a, "usage_pct": u}
        )
        for nid, v in tasks.items():
            recs += _rows(release, "country", iso, "onet_task", nid, {"pct": v})
    return pl.DataFrame(recs, schema=SCHEMA, orient="row")


def _income(countries: dict[str, tuple[float, float]]):
    """{iso: (gdp, wap)} -> the AEI string CSV frames (gdp, wap)."""
    gdp = pl.DataFrame(
        {"iso_alpha_3": list(countries), "gdp_total": [str(g) for g, _ in countries.values()]}
    )
    wap = pl.DataFrame(
        {
            "iso_alpha_3": list(countries),
            "working_age_pop": [str(w) for _, w in countries.values()],
        }
    )
    return gdp, wap


TWO = {
    "AAA": (50.0, 3.0, {"1": 10, "2": 20, "3": 30, "4": 25, "6": 15}),
    "BBB": (45.0, 1.0, {"1": 50, "3": 50}),
}


def test_h4_frame_r45_columns_and_mix():
    gdp, wap = _income({"AAA": (2e12, 4e7), "BBB": (3e11, 1e7)})
    f = RQ.h4_frame_r45(_panel(TWO), "r4", wap=wap, gdp=gdp, gwa=GWA)
    assert f.columns == ["geo_id", "automation_pct", "log_aui", "log_income", "mix", "usage_pct"]
    assert f["geo_id"].to_list() == ["AAA", "BBB"]
    # AAA: s_G1 = 10 + 20/2 = 20, s_G2 = 20/2 + 30 = 40; G3 (15) has no a_bar; task 4 no GWA
    mix_a = (20 * A_G1 + 40 * A_G2) / 60
    mix_b = (50 * A_G1 + 50 * A_G2) / 100
    assert f["mix"].to_list() == pytest.approx([mix_a, mix_b], abs=1e-12)
    assert f["log_aui"].to_list() == pytest.approx(
        [math.log(3.0 / 4e7), math.log(1.0 / 1e7)], abs=1e-12
    )
    assert f["log_income"].to_list() == pytest.approx(
        [math.log(2e12 / 4e7), math.log(3e11 / 1e7)], abs=1e-12
    )
    assert f["automation_pct"].to_list() == [50.0, 45.0]
    assert f["usage_pct"].to_list() == [3.0, 1.0]


@pytest.mark.data
def test_h4_frame_r45_columns_match_plan2_frame():
    """The columns `estimate_h4` reads have the names and dtypes of Plan 2's r6 frame."""
    gdp, wap = _income({"AAA": (2e12, 4e7), "BBB": (3e11, 1e7)})
    f = RQ.h4_frame_r45(_panel(TWO), "r4", wap=wap, gdp=gdp, gwa=GWA)
    ref = upstream.geo_sample().frame
    assert set(f.columns) <= set(ref.columns)
    assert {c: f.schema[c] for c in f.columns} == {c: ref.schema[c] for c in f.columns}


def test_h4_frame_r45_union_over_candidate_task_ids():
    """With a TaskIndex, a task's GWAs are the union over its candidate Task IDs (D14, C-9)."""

    class _Index:
        def task_ids_for(self, text):
            return [3] if text == "task 1" else []  # task 1's statement also carries ID 3

    gdp, wap = _income({"AAA": (2e12, 4e7), "BBB": (3e11, 1e7)})
    f = RQ.h4_frame_r45(_panel(TWO), "r4", wap=wap, gdp=gdp, gwa=GWA, index=_Index())
    # task 1 -> {G1, G2}, split 1/2 each: a_G1 = (1*40 + 1*60)/2, a_G2 = (1*40 + 1*60 + 1*20)/3
    a1, a2 = (40 + 60) / 2, (40 + 60 + 20) / 3
    s1, s2 = 5 + 10, 5 + 10 + 30  # AAA
    assert f["mix"][0] == pytest.approx((s1 * a1 + s2 * a2) / (s1 + s2), abs=1e-12)


def test_h4_frame_r45_exclusions():
    many = {
        **TWO,
        "CCC": (40.0, 2.0, {"4": 100}),  # no GWA -> missing_mix
        "DDD": (None, 2.0, {"1": 100}),  # automation unpublished -> missing_month
        "EEE": (40.0, 2.0, {"1": 100}),  # no income -> missing_income
    }
    gdp, wap = _income(
        {"AAA": (2e12, 4e7), "BBB": (3e11, 1e7), "CCC": (1e11, 1e7), "DDD": (1e11, 1e7)}
    )
    frame, excluded = RQ.h4_sample_r45(_panel(many), "r4", wap=wap, gdp=gdp, gwa=GWA)
    assert frame["geo_id"].to_list() == ["AAA", "BBB"]
    assert excluded == {
        "missing_month": ["DDD"],
        "missing_income": ["EEE"],
        "missing_mix": ["CCC"],
    }


def test_h4_frame_r45_refuses_other_releases():
    gdp, wap = _income({"AAA": (2e12, 4e7)})
    with pytest.raises(ValueError, match="r4 or r5"):
        RQ.h4_frame_r45(_panel(TWO, release="r6"), "r6", wap=wap, gdp=gdp, gwa=GWA)


def _eight():
    rng = np.random.default_rng(7)
    countries, income = {}, {}
    for i in range(8):
        iso = f"C{i:02d}"
        t = {"1": rng.uniform(5, 40), "2": rng.uniform(5, 40), "3": rng.uniform(5, 40)}
        countries[iso] = (float(rng.uniform(30, 60)), float(rng.uniform(0.1, 5)), t)
        income[iso] = (float(rng.uniform(1e10, 1e13)), float(rng.uniform(1e6, 1e8)))
    return countries, income


def test_aui_scale_invariance():
    countries, income = _eight()
    panel = _panel(countries)
    gdp, wap = _income(income)
    gdp3, wap3 = _income({k: (g, 3 * w) for k, (g, w) in income.items()})
    a = upstream.estimate_h4(RQ.h4_frame_r45(panel, "r4", wap=wap, gdp=gdp, gwa=GWA))
    b = upstream.estimate_h4(RQ.h4_frame_r45(panel, "r4", wap=wap3, gdp=gdp3, gwa=GWA))
    for c in ("log_aui", "log_income"):
        assert b.coefs[c].estimate == pytest.approx(a.coefs[c].estimate, abs=1e-10)


# --- records ---------------------------------------------------------------------------------


def _h4_res(n=40, weights=None, b1=-1.2, b2=-0.9, p_family=1e-5):
    coefs = {
        "log_aui": Coef("log_aui", b1, 0.4, b1 - 0.8, b1 + 0.8, 0.003, None),
        "log_income": Coef("log_income", b2, 0.35, b2 - 0.7, b2 + 0.7, 0.009, None),
        "mix": Coef("mix", 1.1, 0.4, 0.3, 1.9, 0.006, None),
    }
    return HypothesisResult(
        hypothesis="H4",
        outcome="automation_pct",
        coefs=coefs,
        p_family=p_family,
        sample={"n": n},
        diagnostics={
            "F": 12.5,
            "df_num": 2,
            "df_denom": n - 4,
            "cov_type": "HC3",
            "estimator": "WLS" if weights else "OLS",
            "weights": weights,
            "tested": ["log_aui", "log_income"],
            "control": "mix",
        },
    )


def test_h4_records():
    recs = RQ.h4_records("R28", "us_states", _h4_res())
    assert [r["estimand"] for r in recs] == ["log_aui", "log_income", RQ.H4_WALD]
    assert RQ.H4_WALD == "joint Wald b1 = b2 = 0"
    b1, b2, w = recs
    assert b1["estimate"] == -1.2 and b1["scale"] == 0.4 and b1["p"] == 0.003
    assert b1["stat"] == pytest.approx(-1.2 / 0.4)
    assert b2["ci_lo"] == pytest.approx(-1.6) and b2["null"] == "coefficient = 0"
    assert w["p"] == 1e-5 and w["estimate"] is None and w["stat"] == 12.5
    assert w["null"] == "b₁ = b₂ = 0" and "not a decision" in w["note"]
    assert all(
        r["n"] == 40 and r["applies_to"] == "H4" and r["label"] == "robustness" for r in recs
    )


# --- R25 -------------------------------------------------------------------------------------


def test_r25_uses_plan2_holm():
    p = dict(zip(RQ.R25_MEMBERS, [0.001, 0.009, 0.02, 0.03, 0.5], strict=True))
    steps = RQ.r25_holm(p)
    assert [steps[m].level for m in RQ.R25_MEMBERS] == pytest.approx(
        [0.0075, 0.009375, 0.0125, 0.01875, 0.0375], abs=1e-15
    )
    assert [steps[m].rejected for m in RQ.R25_MEMBERS] == [True, True, False, False, False]
    assert steps == upstream.holm(p, 0.0375)


def test_r25_members_from_committed():
    res = upstream.committed_rq1()["results"]
    got = RQ.r25_members(res)
    assert list(got) == ["H1a", "H1b", "H3", "H4a", "H4b"]
    assert got["H1a"][1] == "human_education_years_mean" and got["H1b"][1] == "log_wage"
    assert got["H3"][1] == "error_cost"
    assert got["H4a"][1] == "log_aui" and got["H4b"][1] == "log_income"
    for m, (h, name, coef) in got.items():
        assert coef["p"] == res[h]["coefs"][name]["p"], m


# --- the row runners, with Plan 2 stubbed ---------------------------------------------------


def _fake_committed(ps):
    def coef(name, p, est=-1.0):
        return {
            "name": name,
            "estimate": est,
            "se": 0.5,
            "ci_low": est - 1,
            "ci_high": est + 1,
            "p": p,
            "df": 100,
        }

    e, w, g, a, i = ps
    return {
        "results": {
            "H1": {
                "hypothesis": "H1",
                "coefs": {"human_education_years_mean": coef("x", e), "log_wage": coef("y", w)},
                "sample": {"n_rows": 1684},
            },
            "H2": {
                "hypothesis": "H2",
                "coefs": {"trend": coef("trend", 1e-9)},
                "sample": {"n_rows": 5260},
            },
            "H3": {
                "hypothesis": "H3",
                "coefs": {"error_cost": coef("error_cost", g)},
                "sample": {"n_rows": 1689},
            },
            "H4": {
                "hypothesis": "H4",
                "coefs": {
                    "log_aui": coef("log_aui", a),
                    "log_income": coef("log_income", i),
                    "mix": coef("mix", 1e-12),
                },
                "sample": {"n": 113},
            },
        }
    }


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: list[tuple] = []
    countries, income = _eight()
    gdp, wap = _income(income)

    class _Inp:
        panel = pl.concat([_panel(countries, "r4"), _panel(countries, "r5")])
        gdp_country = gdp
        wap_country = wap
        index = None

    def fake_geo_sample(**kw):
        calls.append(("geo_sample", kw))
        frame = pl.DataFrame({"geo_id": ["X"], "usage_pct": [1.0]})
        return upstream.GeoSample(
            frame=frame,
            excluded={"missing_month": ["Q"], "missing_income": [], "missing_mix": []},
            global_automation=48.8,
            m_global=48.8,
        )

    def fake_estimate_h4(frame, **kw):
        calls.append(("estimate_h4", {"n": frame.height, **kw}))
        return _h4_res(n=frame.height, weights=kw.get("weights"))

    def fake_families(level="iwa"):
        calls.append(("task_families", level))
        return GWA

    def forbidden(*a, **k):
        raise AssertionError("another estimator was called")

    monkeypatch.setattr(guards, "require_rq1_run_committed", lambda *a, **k: "abc")
    monkeypatch.setattr(upstream, "geo_sample", fake_geo_sample)
    monkeypatch.setattr(upstream, "estimate_h4", fake_estimate_h4)
    monkeypatch.setattr(upstream, "task_families", fake_families)
    monkeypatch.setattr(upstream, "rq1_inputs", lambda: _Inp())
    monkeypatch.setattr(
        upstream, "committed_rq1", lambda: _fake_committed([0.001, 0.009, 0.02, 0.03, 0.5])
    )
    for name in ("estimate_h1", "estimate_h2", "estimate_h3", "task_rows", "h2_panel"):
        monkeypatch.setattr(upstream, name, forbidden)
    monkeypatch.setattr(rows, "market_variant", forbidden)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    return calls


def test_r28_routes_through_plan2(stubbed):
    rows.run_R28()
    geo = [kw for n, kw in stubbed if n == "geo_sample"]
    assert geo == [{"geo": "us_state"}, {}, {"mix_level": "iwa"}]
    est = [kw for n, kw in stubbed if n == "estimate_h4"]
    assert len(est) == 5
    assert est == [{"n": 1}, {"n": 8}, {"n": 8}, {"n": 1, "weights": "usage_pct"}, {"n": 1}]
    assert ("task_families", "gwa") in stubbed


def test_r28_parts(stubbed):
    csv_path, md_path = rows.run_R28()
    df = pl.read_csv(csv_path)
    parts = ["us_states", "r4_countries", "r5_countries", "usage_weighted", "iwa_mix"]
    assert df["part"].to_list() == [p for p in parts for _ in range(3)]
    assert df["estimand"].to_list() == ["log_aui", "log_income", RQ.H4_WALD] * 5
    md = md_path.read_text(encoding="utf-8")
    assert "C-59" in md and "[default]" in md and upstream.WORDING in md
    assert "| log AUI: " in md and "| joint Wald: " in md
    assert "estimand" not in df["note"][0] and not df["note"][0].startswith("log AUI")


def test_r25_records(stubbed):
    csv_path, md_path = rows.run_R25()
    df = pl.read_csv(csv_path)
    assert df["part"].to_list() == ["H1a", "H1b", "H3", "H4a", "H4b"]
    assert df["applies_to"].to_list() == ["H1", "H1", "H3", "H4", "H4"]
    assert df["p"].to_list() == [0.001, 0.009, 0.02, 0.03, 0.5]
    notes = df["note"].to_list()
    want = [
        ("0.0075", "yes"),
        ("0.009375", "yes"),
        ("0.0125", "no"),
        ("0.01875", "no"),
        ("0.0375", "no"),
    ]
    for n, (level, flag) in zip(notes, want, strict=True):
        assert n.startswith(f"Holm level {level}; rejected under R25: {flag}; not a decision")
    md = md_path.read_text(encoding="utf-8")
    assert "| education: Holm level" in md and upstream.WORDING in md
    assert [kw for kw in stubbed if kw[0] in ("geo_sample", "estimate_h4")] == []


@pytest.mark.parametrize("row_id", TASK13_RUNNERS)
def test_h4_guard(stubbed, monkeypatch, row_id):
    def refuse(*a, **k):
        raise guards.ProtocolError("refused")

    monkeypatch.setattr(guards, "require_rq1_run_committed", refuse)
    monkeypatch.setattr(
        upstream, "committed_rq1", lambda: (_ for _ in ()).throw(AssertionError("read"))
    )
    with pytest.raises(guards.ProtocolError):
        rows.RUNNERS[row_id]()
    assert stubbed == []
