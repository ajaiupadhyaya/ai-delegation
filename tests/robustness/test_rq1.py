"""Plan 4 Task 11: the H1/H3 rows R10 (RQ1 parts), R23 (H1), R24, R26, R27, R31 and R38,
through Plan 2's builders and estimators (stubbed here, except the `data` tests)."""

import csv
import io
import math
import subprocess
from datetime import date

import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.config import ROOT
from aideleg.robustness import guards, report, rows, upstream
from aideleg.robustness import rq1 as RQ
from aideleg.robustness.upstream import Coef, HypothesisResult, TaskRows

APR, MAY = date(2026, 4, 1), date(2026, 5, 1)
JAN = date(2026, 1, 1)
R10_MARKET_COMMIT = "d2da8f1"
TASK11_RUNNERS = ("R10", "R23", "R24", "R26", "R27", "R31", "R38")
H1_NAMES = ("human_education_years_mean", "log_wage")
# Task 11's runners; R23's H1 runner is `run_R23_h1` since Task 12 (RUNNERS["R23"] carries it)
T11_RUNNERS = {**rows.RUNNERS, "R23": rows.run_R23_h1}


def _panel(nodes, release="r6", source="claude_ai"):
    """nodes: (node_id, period_start, {metric: value}); global onet_task rows."""
    recs = [
        (
            release,
            p,
            p,
            source,
            "global",
            "GLOBAL",
            "onet_task",
            0,
            nid,
            f"task {nid}",
            m,
            float(v),
            "collab_v2",
        )
        for nid, p, ms in nodes
        for m, v in ms.items()
    ]
    schema = {
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
    return pl.DataFrame(recs, schema=schema, orient="row")


# --- validation bounds and Consequence of Error -------------------------------------------


def test_validation_bounds_per_period_then_averaged():
    panel = _panel(
        [
            ("1", APR, {"pct": 1, "validation_pct": 60, "none_pct": 10}),
            ("1", MAY, {"pct": 1, "validation_pct": 40, "none_pct": 30}),
        ]
    )
    out = RQ.validation_bounds(panel, release="r6", source="claude_ai")
    assert out.columns == ["task_node", "validation_share_all_lb", "validation_share_all_ub"]
    (row,) = out.iter_rows(named=True)
    assert row["task_node"] == "1"
    assert row["validation_share_all_lb"] == pytest.approx(41.0, abs=1e-12)
    assert row["validation_share_all_ub"] == pytest.approx(61.0, abs=1e-12)


def test_validation_bounds_single_period():
    panel = _panel(
        [("7", JAN, {"pct": 2, "validation_pct": 60, "not_classified_pct": 4, "none_pct": 6})],
        release="r4",
    )
    out = RQ.validation_bounds(panel, release="r4", source="claude_ai")
    (row,) = out.iter_rows(named=True)
    assert row["validation_share_all_lb"] == pytest.approx(54.0, abs=1e-12)
    assert row["validation_share_all_ub"] == pytest.approx(64.0, abs=1e-12)


def test_validation_bounds_null_unless_every_component_published():
    panel = _panel(
        [("7", JAN, {"pct": 2, "validation_pct": 60, "none_pct": 6})],
        release="r4",
    )
    (row,) = RQ.validation_bounds(panel, release="r4", source="claude_ai").iter_rows(named=True)
    assert row["validation_share_all_lb"] is None and row["validation_share_all_ub"] is None


def _tr(rows_df: pl.DataFrame) -> TaskRows:
    return TaskRows(rows_df, total_weight=float(rows_df["weight"].sum()))


def test_with_validation_bounds_left_join():
    tr = _tr(pl.DataFrame({"task_node": ["1", "2"], "weight": [1.0, 2.0]}))
    b = pl.DataFrame(
        {"task_node": ["1"], "validation_share_all_lb": [3.0], "validation_share_all_ub": [5.0]}
    )
    out = RQ.with_validation_bounds(tr, b)
    assert out.total_weight == tr.total_weight
    assert out.rows["validation_share_all_lb"].to_list() == [3.0, None]


def test_with_coe_zscores_across_occupations():
    tr = _tr(
        pl.DataFrame(
            {
                "task_node": ["1", "2", "3", "4", "5"],
                "soc6": ["11-1011", "13-2011", "13-2011", "23-1011", "99-9999"],
                "weight": [1.0, 1.0, 1.0, 1.0, 1.0],
            }
        )
    )
    coe = pl.DataFrame(
        {"soc6": ["11-1011", "13-2011", "23-1011", "45-0000"], "coe": [1.0, 2.0, 3.0, 9.0]}
    )
    out = RQ.with_coe(tr, coe).rows
    got = out["coe"].to_list()
    z = math.sqrt(1.5)
    assert got[0] == pytest.approx(-z, abs=1e-12)
    assert got[1] == pytest.approx(0.0, abs=1e-12)
    assert got[2] == pytest.approx(0.0, abs=1e-12)
    assert got[3] == pytest.approx(z, abs=1e-12)
    assert got[4] is None
    assert out.height == tr.rows.height


# --- records ------------------------------------------------------------------------------


def _coef(name, est, se, p, df=100):
    return Coef(name, est, se, est - 2 * se, est + 2 * se, p, df)


def _res(h="H1", signs=(-1.0, -1.0), ps=(0.01, 0.02), outcome=None, notes=()):
    names = H1_NAMES if h == "H1" else ("error_cost",)
    coefs = {n: _coef(n, s * 1.5, 0.5, p) for n, s, p in zip(names, signs, ps, strict=False)}
    return HypothesisResult(
        hypothesis=h,
        outcome=outcome or ("automation_pct" if h == "H1" else "validation_pct"),
        coefs=coefs,
        p_family=max(ps[: len(names)]),
        sample={"n_rows": 120, "g_occ": 30, "g_task": 80, "df_inference": 29},
        drops={"unmatched_task": 1.25, "zero_weight": 0.0, "wage_suppressed": 0.5},
        diagnostics={
            "df_inference": 29,
            "g_occ": 30,
            "g_task": 80,
            "se_oneway_occ": {n: 0.25 for n in names},
            "p_oneway_occ": {n: 0.004 + i / 100 for i, n in enumerate(names)},
        },
        notes=list(notes),
    )


def test_rq1_records_schema_and_p_h1():
    res = _res(notes=("non-PSD rule applied to [a, b]: smallest eigenvalue -1",))
    recs = RQ.rq1_records("R24", "r4", res)
    for r in recs:
        report.check_record(r)
    assert [r["estimand"] for r in recs] == [*H1_NAMES, "p_H1"]
    c = recs[0]
    assert c["estimate"] == -1.5 and c["scale"] == 0.5 and c["stat"] == pytest.approx(-3.0)
    assert (c["ci_lo"], c["ci_hi"], c["p"], c["n"]) == (-2.5, -0.5, 0.01, 120)
    assert "df 100" in c["note"] and "G_occ 30" in c["note"] and "non-PSD" in c["note"]
    assert "unmatched_task 1.25%" in c["dropped"] and "zero_weight" not in c["dropped"]
    assert recs[-1]["p"] == res.p_family and recs[-1]["estimate"] is None
    h3 = RQ.rq1_records("R24", "r4", _res("H3"))
    assert [r["estimand"] for r in h3] == ["error_cost"]


def test_rq1_records_oneway_occ():
    res = _res()
    recs = RQ.rq1_records("R38", "oneway_occ", res, se_key="se_oneway_occ")
    from scipy import stats

    c = recs[0]
    assert c["scale"] == 0.25 and c["p"] == 0.004
    half = stats.t.ppf(0.975, 29) * 0.25
    assert c["ci_lo"] == pytest.approx(-1.5 - half) and c["ci_hi"] == pytest.approx(-1.5 + half)
    assert "df 29" in c["note"]
    assert recs[-1]["p"] == max(res.diagnostics["p_oneway_occ"].values())


# --- the row runners, with Plan 2 stubbed -------------------------------------------------


def _fake_tr(**kw):
    df = pl.DataFrame(
        {
            "task_node": ["1", "2"],
            "soc6": ["11-1011", "13-2011"],
            "weight": [1.0, 1.0],
        }
    )
    return TaskRows(
        df,
        2.0,
        release=kw.get("release", "r6"),
        source=kw.get("source", "claude_ai"),
        family_level=kw.get("family_level", "iwa"),
    )


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: list[tuple] = []

    def fake_task_rows(**kw):
        calls.append(("task_rows", kw))
        return _fake_tr(**kw)

    def fake_h1(tr, outcome="automation_pct", **kw):
        calls.append(("estimate_h1", {"outcome": outcome, **kw}))
        return _res("H1", outcome=outcome)

    def fake_h3(tr, outcome="validation_pct", indicator="error_cost", covariates=()):
        calls.append(
            ("estimate_h3", {"outcome": outcome, "indicator": indicator, "covariates": covariates})
        )
        r = _res("H3", outcome=outcome)
        r.coefs = {indicator: r.coefs["error_cost"]}
        for c in covariates:
            r.coefs[c] = _coef(c, 0.1, 0.1, 0.3)
        return r

    def forbidden(*a, **k):
        raise AssertionError("another estimator was called")

    class _Inp:
        panel = _panel([("1", APR, {"pct": 1, "validation_pct": 50, "none_pct": 2})])

    monkeypatch.setattr(guards, "require_rq1_run_committed", lambda *a, **k: "abc")
    monkeypatch.setattr(upstream, "task_rows", fake_task_rows)
    monkeypatch.setattr(upstream, "estimate_h1", fake_h1)
    monkeypatch.setattr(upstream, "estimate_h3", fake_h3)
    monkeypatch.setattr(upstream, "estimate_h2", forbidden)
    monkeypatch.setattr(upstream, "estimate_h4", forbidden)
    monkeypatch.setattr(upstream, "rq1_inputs", lambda: _Inp())
    monkeypatch.setattr(
        upstream,
        "committed_rq1",
        lambda: {"results": {"H1": {"coefs": {n: {"estimate": -1.0} for n in H1_NAMES}}}},
    )
    monkeypatch.setattr(
        RQ,
        "consequence_of_error",
        lambda: pl.DataFrame({"soc6": ["11-1011", "13-2011"], "coe": [3.0, 5.0]}),
    )
    monkeypatch.setattr(rows, "market_variant", forbidden)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    _seed_r10(tmp_path)
    return calls


def _committed_r10(rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{R10_MARKET_COMMIT}:docs/results/robustness/{rel}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _seed_r10(out_dir):
    (out_dir / "R10.csv").write_text(_committed_r10("R10.csv"), encoding="utf-8")
    (out_dir / "R10.md").write_text(_committed_r10("R10.md"), encoding="utf-8")


def _market_lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    return [lines[0], *(ln for ln in lines if ln.startswith("R10,market_"))]


def test_rows_route_through_plan2(stubbed):
    rows.run_R24()
    rows.run_R26()
    tr_calls = [kw for name, kw in stubbed if name == "task_rows"]
    assert tr_calls == [
        {"release": "r4"},
        {"release": "r5"},
        {"source": "1p_api"},
        {"family_level": "gwa"},
        {"family_level": "dwa"},
    ]
    est = [name for name, _ in stubbed if name != "task_rows"]
    assert est == ["estimate_h1", "estimate_h3"] * 5


def test_row_calls(stubbed):
    rows.run_R10()
    rows.run_R23_h1()
    rows.run_R27()
    rows.run_R31()
    est = [(n, kw) for n, kw in stubbed if n != "task_rows"]
    assert est[:4] == [
        ("estimate_h1", {"outcome": "automation_share_all_lb"}),
        ("estimate_h1", {"outcome": "automation_share_all_ub"}),
        (
            "estimate_h3",
            {"outcome": "validation_share_all_lb", "indicator": "error_cost", "covariates": ()},
        ),
        (
            "estimate_h3",
            {"outcome": "validation_share_all_ub", "indicator": "error_cost", "covariates": ()},
        ),
    ]
    assert est[4] == ("estimate_h1", {"outcome": "ai_autonomy_mean"})
    assert est[5] == (
        "estimate_h3",
        {"outcome": "validation_pct", "indicator": "coe", "covariates": ()},
    )
    assert est[6] == (
        "estimate_h3",
        {
            "outcome": "validation_pct",
            "indicator": "error_cost",
            "covariates": ("human_education_years_mean", "log_wage"),
        },
    )
    assert all(kw == {} for n, kw in stubbed if n == "task_rows")


@pytest.mark.parametrize("row_id", TASK11_RUNNERS)
def test_rq1_guard(stubbed, monkeypatch, row_id):
    def refuse(*a, **k):
        raise guards.ProtocolError("refused")

    monkeypatch.setattr(guards, "require_rq1_run_committed", refuse)
    with pytest.raises(guards.ProtocolError):
        T11_RUNNERS[row_id]()
    assert not any(n == "task_rows" for n, _ in stubbed)


@pytest.mark.parametrize("row_id", TASK11_RUNNERS)
def test_rows_write_parts(stubbed, row_id):
    want = {
        "R10": {"market_lb", "market_ub", "h1_lb", "h1_ub", "h3_lb", "h3_ub"},
        "R23": {"h1"},
        "R24": {"r4", "r5", "r6_1p_api"},
        "R26": {"gwa", "dwa"},
        "R27": {"coe"},
        "R31": {"covariates"},
        "R38": {"oneway_occ"},
    }[row_id]
    csv_path, md_path = T11_RUNNERS[row_id]()
    df = pl.read_csv(csv_path)
    assert set(df["part"]) == want
    md = md_path.read_text(encoding="utf-8")
    assert upstream.WORDING in md


def test_r10_market_rows_carried_byte_identical(stubbed):
    csv_path, md_path = rows.run_R10()
    got = csv_path.read_text(encoding="utf-8")
    assert _market_lines(got) == _market_lines(_committed_r10("R10.csv"))
    md = md_path.read_text(encoding="utf-8")
    old_notes = [ln for ln in _committed_r10("R10.md").splitlines() if ln.startswith("- ")]
    for ln in old_notes:
        assert md.count(ln) == 1, ln
    assert "C-57" in md
    # idempotent: a second run reads the market rows back and writes the same files
    rows.run_R10()
    assert csv_path.read_text(encoding="utf-8") == got
    assert md_path.read_text(encoding="utf-8") == md


def test_r10_committed_market_rows_unchanged():
    """The committed R10.csv keeps Task 8's market rows byte for byte."""
    now = (ROOT / "docs/results/robustness/R10.csv").read_text(encoding="utf-8")
    assert _market_lines(now) == _market_lines(_committed_r10("R10.csv"))
    head = next(csv.reader(io.StringIO(now)))
    assert head == report.ROBUSTNESS_COLUMNS


def _r23_md(stubbed_calls, monkeypatch, signs, ps):
    def fake_h1(tr, outcome="automation_pct", **kw):
        return _res("H1", signs=signs, ps=ps, outcome=outcome)

    monkeypatch.setattr(upstream, "estimate_h1", fake_h1)
    _, md = rows.run_R23_h1()
    return md.read_text(encoding="utf-8")


def test_r23_disagreement_sentence_conditional(stubbed, monkeypatch):
    # the stubbed committed H1 coefficients are both negative
    opposite = _r23_md(stubbed, monkeypatch, (1.0, 1.0), (0.01, 0.02))
    assert RQ.R23_DISAGREE in opposite
    same = _r23_md(stubbed, monkeypatch, (-1.0, -1.0), (0.01, 0.02))
    assert RQ.R23_DISAGREE not in same
    not_sig = _r23_md(stubbed, monkeypatch, (1.0, 1.0), (0.01, 0.2))
    assert RQ.R23_DISAGREE not in not_sig
    one_side = _r23_md(stubbed, monkeypatch, (1.0, -1.0), (0.01, 0.02))
    assert RQ.R23_DISAGREE not in one_side


def test_r23_condition_function():
    prim = {n: -1.0 for n in H1_NAMES}
    assert RQ.r23_disagrees(_res(signs=(1.0, 1.0), ps=(0.04, 0.01)), prim)
    assert not RQ.r23_disagrees(_res(signs=(1.0, 1.0), ps=(0.05, 0.01)), prim)
    assert not RQ.r23_disagrees(_res(signs=(-1.0, 1.0), ps=(0.01, 0.01)), prim)


# --- data: R38 reproduces Plan 2's committed one-way diagnostics --------------------------


@pytest.mark.data
def test_r38_matches_plan2_p_oneway_occ():
    committed = upstream.committed_rq1()["results"]
    tr = upstream.task_rows()
    for h, est in (("H1", upstream.estimate_h1), ("H3", upstream.estimate_h3)):
        recs = RQ.rq1_records("R38", "oneway_occ", est(tr), se_key="se_oneway_occ")
        want = committed[h]["diagnostics"]["p_oneway_occ"]
        got = {r["estimand"]: r["p"] for r in recs if r["estimand"] in want}
        assert set(got) == set(want)
        for n, p in want.items():
            assert got[n] == pytest.approx(p, rel=1e-12, abs=0.0), (h, n)


# --- review fixes (PAP §11 C-77, C-78) ---------------------------------------------------


def test_r23_sign_line_printed_either_way(stubbed, monkeypatch):
    for signs, s in (((1.0, 1.0), "opposite"), ((-1.0, -1.0), "same")):
        md = _r23_md(stubbed, monkeypatch, signs, (0.0001, 0.2))
        b = report.fmt_pp(signs[0] * 1.5)
        assert (
            f"Sign check against the committed primary H1 (P-RQ1): education R23 {b} vs primary "
            f"-1.00, {s} sign, p < 0.001; log wage R23 {report.fmt_pp(signs[1] * 1.5)} vs "
            f"primary -1.00, {s} sign, p 0.200 (PAP §11 C-77)"
        ) in md
    assert "scale points" in md and "pp of the outcome share" not in md.split("## Results")[0]


def test_md_labels_coefficients_csv_plain(stubbed):
    csv_path, md_path = rows.run_R31()
    md = md_path.read_text(encoding="utf-8")
    for lab in ("| error cost: SE", "| education: SE", "| log wage: SE"):
        assert lab in md, lab
    df = pl.read_csv(csv_path)
    assert all(n.startswith("SE ") for n in df["note"].to_list())
    _, md10 = rows.run_R10()
    text = md10.read_text(encoding="utf-8")
    assert "| p_H1: p_H1 = max" in text and "| education: SE" in text
    assert "n_dropped` is not reported for RQ1 rows" in text and "C-78" in text
    assert "`none_pct`" in text
