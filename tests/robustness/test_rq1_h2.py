"""Plan 4 Task 12: the H2 rows R22, R23 (H2 part), R36 and R37, through Plan 2's
`build_h2_panel` and `estimate_h2` (stubbed here) and Plan 4's own `within_r6` (R37)."""

import subprocess
from datetime import date

import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.config import ROOT
from aideleg.robustness import guards, report, rows, upstream
from aideleg.robustness import rq1 as RQ
from aideleg.robustness.upstream import Coef, HypothesisResult

APR, MAY = date(2026, 4, 1), date(2026, 5, 1)
R23_H1_COMMIT = "61b0625"
TASK12_RUNNERS = ("R22", "R23", "R36", "R37")
R22_METRICS = (
    "augmentation_pct",
    "directive_pct",
    "feedback_loop_pct",
    "task_iteration_pct",
    "validation_pct",
    "learning_pct",
)
ALL = ("r2", "r3", "r4", "r5", "r6")


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


def _h2_res(
    releases=("r2", "r3", "r4", "r5"),
    outcome="automation_pct",
    est=1.2,
    p=0.01,
    p_wild=0.0046,
    r6_indicator=False,
):
    k = len(releases)
    coefs = {"trend": Coef("trend", est, 0.4, est - 0.8, est + 0.8, p, 79)}
    if r6_indicator:
        coefs["r6"] = Coef("r6", -0.5, 0.3, -1.1, 0.1, 0.1, 79)
    return HypothesisResult(
        hypothesis="H2",
        outcome=outcome,
        coefs=coefs,
        p_family=p,
        sample={"n_tasks": 80, "n_rows": 80 * k, "releases": list(releases), "times": {}},
        diagnostics={
            "p_wild": p_wild,
            "n_wild_draws": 6**k,
            "p_release_label": 0.25,
            "n_release_orderings": 24,
            "df_inference": 79,
            "g_task": 80,
            "r6_indicator": r6_indicator,
            "release_effects": {},
        },
        notes=[],
    )


# --- h2_records ---------------------------------------------------------------------------


def test_weight_vectors_count():
    res = _h2_res(releases=("r4", "r5", "r6"))
    assert res.diagnostics["n_wild_draws"] == 216
    (rec,) = RQ.h2_records("R23", "h2", res, label="robustness")
    assert "6^3 = 216" in rec["note"]


def test_h2_records_schema_and_rule_flag():
    (rec,) = RQ.h2_records("R36", "publication", _h2_res(), label="robustness")
    report.check_record(rec)
    assert rec["estimand"] == "beta (pp per year)"
    assert (rec["estimate"], rec["scale"], rec["p"]) == (1.2, 0.4, 0.01)
    assert rec["stat"] == pytest.approx(3.0) and rec["n"] == 320 and rec["applies_to"] == "H2"
    assert rec["note"].startswith(
        "wild-bootstrap p = 0.005; weight vectors = 6^4 = 1296; would meet the H2 rule "
        "(both p <= 0.0125 and beta > 0): yes; not a decision"
    )
    no = [
        _h2_res(p=0.02),  # task-clustered p too large
        _h2_res(p_wild=0.02),  # wild p too large
        _h2_res(est=-1.2),  # wrong sign
        _h2_res(p=float("nan")),
    ]
    for r in no:
        (x,) = RQ.h2_records("R36", "publication", r, label="robustness")
        assert "(both p <= 0.0125 and beta > 0): no; not a decision" in x["note"]
    # exact level, as PAP §11 C-24: p = 0.0125 meets it
    (edge,) = RQ.h2_records("R36", "x", _h2_res(p=0.0125, p_wild=0.0125), label="robustness")
    assert "beta > 0): yes" in edge["note"]
    (aut,) = RQ.h2_records("R23", "h2", _h2_res(outcome="ai_autonomy_mean"), label="robustness")
    assert aut["unit"] == RQ.H2_AUTONOMY_UNIT and rec["unit"] == RQ.H2_UNIT


def test_h2_records_refuses_inconsistent_draws():
    res = _h2_res()
    res.diagnostics["n_wild_draws"] = 100
    with pytest.raises(ValueError):
        RQ.h2_records("R36", "x", res, label="robustness")


# --- within_r6 (R37) ----------------------------------------------------------------------


def test_within_r6_hand_case():
    panel = _panel(
        [
            ("1", APR, {"pct": 1, "automation_pct": 40}),
            ("1", MAY, {"pct": 1, "automation_pct": 50}),
            ("2", APR, {"pct": 1, "automation_pct": 60}),
            ("2", MAY, {"pct": 1, "automation_pct": 64}),
            ("3", APR, {"pct": 1, "automation_pct": 10}),  # April only: excluded
            ("3", MAY, {"pct": 1}),
        ]
    )
    out = RQ.within_r6(panel)
    assert {"estimate", "se", "ci_lo", "ci_hi", "p", "n_tasks"} <= set(out)
    assert out["estimate"] == pytest.approx(7.0)
    assert out["n_tasks"] == 2
    assert out["ci_lo"] < 7.0 < out["ci_hi"]


def test_within_r6_weights_mean_pct():
    panel = _panel(
        [
            ("1", APR, {"pct": 1, "automation_pct": 40}),
            ("1", MAY, {"pct": 3, "automation_pct": 50}),  # weight 2, change 10
            ("2", APR, {"pct": 2, "automation_pct": 60}),
            ("2", MAY, {"pct": 4, "automation_pct": 64}),  # weight 3, change 4
            ("3", APR, {"pct": 1, "automation_pct": 20}),
            ("3", MAY, {"pct": 1, "automation_pct": 21}),  # weight 1, change 1
        ]
    )
    out = RQ.within_r6(panel)
    assert out["estimate"] == pytest.approx((2 * 10 + 3 * 4 + 1 * 1) / 6)


@pytest.mark.filterwarnings("ignore:invalid value encountered:RuntimeWarning")
def test_within_r6_matches_plan2_h2_estimator_on_two_periods():
    """Two periods with task FE and fixed task weights is Plan 2's H2 regression with t in
    {0, 1}: the same β, task-clustered SE and p."""
    vals = [(40, 50, 1.0), (60, 64, 2.0), (20, 19, 0.5), (33, 41, 1.5), (70, 71, 1.0)]
    nodes, frame = [], []
    for i, (a, m, w) in enumerate(vals):
        nodes += [
            (str(i), APR, {"pct": w, "automation_pct": a}),
            (str(i), MAY, {"pct": w, "automation_pct": m}),
        ]
        frame += [(str(i), "r5", 0.0, float(a), w), (str(i), "r6", 1.0, float(m), w)]
    out = RQ.within_r6(_panel(nodes))
    df = pl.DataFrame(
        frame, schema=["task_node", "release", "t", "automation_pct", "weight"], orient="row"
    )
    c = upstream.estimate_h2(df).coefs["trend"]
    assert out["estimate"] == pytest.approx(c.estimate, rel=1e-10)
    assert out["se"] == pytest.approx(c.se, rel=1e-10)
    assert out["p"] == pytest.approx(c.p, rel=1e-10)
    assert (out["ci_lo"], out["ci_hi"]) == pytest.approx((c.ci_low, c.ci_high), rel=1e-10)


# --- the row runners, with Plan 2 stubbed -------------------------------------------------


def _committed(rel: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), "show", f"{R23_H1_COMMIT}:docs/results/robustness/{rel}"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _h1_lines(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    return [lines[0], *(ln for ln in lines if ln.startswith("R23,h1,"))]


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: list[tuple] = []

    def fake_h2_panel(**kw):
        calls.append(("h2_panel", kw))
        return pl.DataFrame({"releases": [list(kw.get("releases", ("r2", "r3", "r4", "r5")))]})

    def fake_estimate_h2(df, outcome="automation_pct", **kw):
        calls.append(("estimate_h2", {"outcome": outcome, **kw}))
        return _h2_res(releases=tuple(df["releases"][0]), outcome=outcome, **kw)

    def forbidden(*a, **k):
        raise AssertionError("another estimator was called")

    class _Inp:
        panel = _panel(
            [
                ("1", APR, {"pct": 1, "automation_pct": 40}),
                ("1", MAY, {"pct": 1, "automation_pct": 50}),
                ("2", APR, {"pct": 1, "automation_pct": 60}),
                ("2", MAY, {"pct": 1, "automation_pct": 64}),
            ]
        )

    monkeypatch.setattr(guards, "require_rq1_run_committed", lambda *a, **k: "abc")
    monkeypatch.setattr(upstream, "h2_panel", fake_h2_panel)
    monkeypatch.setattr(upstream, "estimate_h2", fake_estimate_h2)
    for name in ("estimate_h1", "estimate_h3", "estimate_h4", "task_rows"):
        monkeypatch.setattr(upstream, name, forbidden)
    monkeypatch.setattr(upstream, "rq1_inputs", lambda: _Inp())
    monkeypatch.setattr(rows, "market_variant", forbidden)
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path)
    for rel in ("R23.csv", "R23.md"):
        (tmp_path / rel).write_text(_committed(rel), encoding="utf-8")
    return calls


def test_h2_rows_route_through_plan2(stubbed):
    rows.run_R22()
    rows.run_R36()
    panels = [kw for n, kw in stubbed if n == "h2_panel"]
    assert panels == [
        {"releases": ALL},
        {"releases": ALL},
        {"balanced": False},
        *({"outcome": m} for m in R22_METRICS),
        {"source": "1p_api", "releases": ("r3", "r4", "r5")},
        {"time_basis": "publication"},
    ]
    est = [kw for n, kw in stubbed if n == "estimate_h2"]
    assert est == [
        {"outcome": "automation_pct"},
        {"outcome": "automation_pct", "r6_indicator": True},
        {"outcome": "automation_pct"},
        *({"outcome": m} for m in R22_METRICS),
        {"outcome": "automation_pct"},
        {"outcome": "automation_pct"},
    ]


def test_r23_h2_call(stubbed):
    rows.run_R23()
    assert stubbed == [
        ("h2_panel", {"releases": ("r4", "r5", "r6"), "outcome": "ai_autonomy_mean"}),
        ("estimate_h2", {"outcome": "ai_autonomy_mean"}),
    ]


def test_r22_parts(stubbed):
    csv_path, md_path = rows.run_R22()
    df = pl.read_csv(csv_path)
    assert df["part"].to_list() == [
        "all_r2_r6",
        "all_r2_r6_r6dummy",
        "unbalanced",
        *R22_METRICS,
        "api_r3_r5",
    ]
    lab = dict(zip(df["part"], df["label"], strict=True))
    assert lab["all_r2_r6"] == rows.R22_CONFOUNDED
    assert lab["all_r2_r6_r6dummy"] == "robustness" and lab["unbalanced"] == "robustness"
    md = md_path.read_text(encoding="utf-8")
    assert "C-56" in md and upstream.WORDING in md
    assert "| trend β: wild-bootstrap p" in md
    assert all(n.startswith("wild-bootstrap p") for n in df["note"].to_list())


@pytest.mark.parametrize("row_id", TASK12_RUNNERS)
def test_h2_guard(stubbed, monkeypatch, row_id):
    def refuse(*a, **k):
        raise guards.ProtocolError("refused")

    monkeypatch.setattr(guards, "require_rq1_run_committed", refuse)
    with pytest.raises(guards.ProtocolError):
        rows.RUNNERS[row_id]()
    assert stubbed == []


def test_r23_h1_rows_carried_byte_identical(stubbed):
    csv_path, md_path = rows.run_R23()
    got = csv_path.read_text(encoding="utf-8")
    assert _h1_lines(got) == _h1_lines(_committed("R23.csv"))
    df = pl.read_csv(csv_path)
    assert df["part"].to_list() == ["h1", "h1", "h1", "h2"]
    h2 = df.filter(pl.col("part") == "h2").row(0, named=True)
    assert h2["label"] == rows.R23_H2_LABEL and h2["applies_to"] == "H2"
    md = md_path.read_text(encoding="utf-8")
    old = _committed("R23.md")
    for ln in (x for x in old.splitlines() if x.startswith("- ")):
        assert md.count(ln) == 1, ln
    old_table = [x for x in old.splitlines() if x.startswith("| h1 |")]
    assert len(old_table) == 3 and all(md.count(x) == 1 for x in old_table)
    assert "scale points per year" in md
    # idempotent: a second run carries the same H1 rows and notes and writes the same files
    rows.run_R23()
    assert csv_path.read_text(encoding="utf-8") == got
    assert md_path.read_text(encoding="utf-8") == md


def test_r23_carry_refuses_without_h1(stubbed, tmp_path):
    (tmp_path / "R23.csv").write_text(",".join(report.ROBUSTNESS_COLUMNS) + "\n", encoding="utf-8")
    with pytest.raises(ValueError):
        rows.run_R23()


def test_r23_committed_h1_rows_unchanged():
    """The committed R23.csv keeps Task 11's H1 rows (61b0625) byte for byte."""
    now = (ROOT / "docs/results/robustness/R23.csv").read_text(encoding="utf-8")
    assert _h1_lines(now) == _h1_lines(_committed("R23.csv"))


def test_r37_record(stubbed):
    csv_path, md_path = rows.run_R37()
    df = pl.read_csv(csv_path)
    (r,) = df.rows(named=True)
    assert r["estimand"] == "May minus April (pp)" and r["label"] == "robustness; descriptive"
    assert r["estimate"] == pytest.approx(7.0) and r["applies_to"] == "H2"
    assert "wild" not in (r["note"] or "")
    assert "n_tasks 2" in r["note"]
    assert not any(n == "estimate_h2" for n, _ in stubbed)
