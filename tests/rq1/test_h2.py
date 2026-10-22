"""H2 (PAP §4.2, §5, D2, D22), checked on synthetic data only."""

import math
from datetime import date

import numpy as np
import polars as pl
import pytest
import statsmodels.api as sm
import synth

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.config import SEED
from aideleg.rq1 import h2

H2_TIMES, h2_frame = synth.H2_TIMES, synth.h2_frame

# The real claude_ai windows of r2-r5 (period_start, period_end), and r6's two months.
WINDOWS = {"r2": [(date(2025, 2, 24), date(2025, 3, 4))],
           "r3": [(date(2025, 8, 4), date(2025, 8, 11))],
           "r4": [(date(2025, 11, 13), date(2025, 11, 20))],
           "r5": [(date(2026, 2, 5), date(2026, 2, 12))],
           "r6": [(date(2026, 4, 1), date(2026, 5, 1)), (date(2026, 5, 1), date(2026, 6, 1))]}
R2_R5 = ("r2", "r3", "r4", "r5")


def _panel(cells):
    """cells: (release, node_id, {metric: value or None}); every period of the release."""
    recs = []
    for rel, nid, ms in cells:
        for start, end in WINDOWS[rel]:
            for m, v in ms.items():
                recs.append((rel, start, end, "claude_ai", "global", "GLOBAL", "onet_task", 0,
                             nid, f"task {nid}", m, None if v is None else float(v),
                             "collab_v2"))
    schema = {c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                  else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS}
    return pl.DataFrame(recs, schema=schema, orient="row")


def _cell(rel, nid, pct, auto, **more):
    return (rel, nid, {"pct": pct, "automation_pct": auto, **more})


@pytest.fixture
def fixture_panel():
    """T1 all four published; T2 r4 outcome null (pct kept); T3 no r5 row; T4 r2 only;
    an `unmatched:none` node in every release; r6 rows for T1-T3 (T2 May only)."""
    cells = []
    for i, r in enumerate(R2_R5):
        cells.append(_cell(r, "T1", 1.0 + i, 40.0 + 2 * i, validation_pct=20.0 - i))
        cells.append(_cell(r, "T2", 2.0 * (i + 1), None if r == "r4" else 30.0 + i,
                           validation_pct=None if r == "r4" else 25.0 + 0.5 * i))
        if r != "r5":
            cells.append(_cell(r, "T3", 0.5, 50.0 - i, validation_pct=10.0 + i * i))
        if r == "r2":
            cells.append(_cell(r, "T4", 3.0, 60.0, validation_pct=5.0))
        cells.append(_cell(r, "unmatched:none", 5.0, 10.0, validation_pct=10.0))
    panel = _panel(cells)
    r6 = []
    for nid, auto, val in (("T1", 49.0, 15.0), ("T3", 47.0, 18.0)):
        r6.append(_cell("r6", nid, 2.0, auto, validation_pct=val))
    r6p = _panel(r6)
    # T2 in r6: published in May only (April pct and values null).
    may = _panel([_cell("r6", "T2", 4.0, 35.0, validation_pct=28.0)]).filter(
        pl.col("period_start") == date(2026, 5, 1))
    apr = _panel([_cell("r6", "T2", None, None, validation_pct=None)]).filter(
        pl.col("period_start") == date(2026, 4, 1))
    return pl.concat([panel, r6p, may, apr])


def test_release_times_midpoints(fixture_panel):
    t = h2.release_times(fixture_panel, R2_R5)
    assert t == pytest.approx(H2_TIMES, abs=1e-12)
    assert set(t) == set(R2_R5)


def test_release_times_publication(fixture_panel):
    t = h2.release_times(fixture_panel, R2_R5, basis="publication")
    assert t == pytest.approx({"r2": 0.0, "r3": 0.47091033538672145, "r4": 0.8049281314168378,
                               "r5": 0.9911019849418207}, abs=1e-12)
    t6 = h2.release_times(fixture_panel, ("r2", "r6"))
    assert t6["r6"] == pytest.approx(1.1704312114989732, abs=1e-12)


def test_balanced_panel_drops_tasks_missing_a_release(fixture_panel):
    bal = h2.build_h2_panel(fixture_panel)
    assert bal.columns == ["task_node", "release", "t", "automation_pct", "weight"]
    assert set(bal["task_node"]) == {"T1"} and bal.height == 4

    unb = h2.build_h2_panel(fixture_panel, balanced=False)
    counts = dict(unb.group_by("task_node").len().iter_rows())
    assert counts == {"T1": 4, "T2": 3, "T3": 3}
    assert unb["automation_pct"].null_count() == 0
    t2 = unb.filter(pl.col("task_node") == "T2")
    assert t2["weight"].unique().to_list() == [pytest.approx((2 + 4 + 6 + 8) / 4)]
    t3 = unb.filter(pl.col("task_node") == "T3")
    assert t3["weight"].unique().to_list() == [pytest.approx(1.5 / 4)]  # r5 unpublished = 0
    assert sorted(t2["release"]) == ["r2", "r3", "r5"]
    assert t2.filter(pl.col("release") == "r3")["t"].item() == pytest.approx(H2_TIMES["r3"])


def test_weights_fixed_per_task(fixture_panel):
    bal = h2.build_h2_panel(fixture_panel)
    assert bal["weight"].to_list() == [pytest.approx(2.5)] * 4  # pct 1, 2, 3, 4


def _sm_fit(df, outcome, extra=()):
    task = np.unique(df["task_node"].to_numpy(), return_inverse=True)[1]
    dummies = (task[:, None] == np.arange(task.max() + 1)).astype(float)
    X = np.column_stack([df["t"].to_numpy(), *[df[c].to_numpy() for c in extra], dummies])
    return sm.WLS(df[outcome].to_numpy(), X, weights=df["weight"].to_numpy()).fit(
        cov_type="cluster", cov_kwds={"groups": task}, use_t=True)


@pytest.mark.parametrize("balanced", [True, False])
def test_within_matches_statsmodels_dummy_fit(balanced):
    rng = np.random.default_rng(SEED)
    n = 30
    alpha = rng.normal(0, 5, n)
    vals = {r: 2.0 * H2_TIMES[r] + rng.normal(0, 1, n) for r in R2_R5}
    df = h2_frame(alpha, vals, weight=rng.uniform(0.5, 3.0, n))
    if not balanced:  # tasks with 1-3 missing releases, including one single-row task
        keep = rng.random(df.height) > 0.3
        keep[:4] = [True, False, False, False]
        df = df.filter(pl.Series(keep))
    df = df.with_columns(r6=pl.Series(rng.normal(size=df.height)))
    fit = _sm_fit(df, "automation_pct", extra=("r6",))
    task = np.unique(df["task_node"].to_numpy(), return_inverse=True)[1]
    X = df.select("t", "r6").to_numpy()
    beta, cov = h2.clustered_within(df["automation_pct"].to_numpy(), X,
                                    df["weight"].to_numpy(), task, tested=0)
    np.testing.assert_allclose(beta, fit.params[:2], rtol=1e-10)
    np.testing.assert_allclose(cov, fit.cov_params()[:2, :2], rtol=1e-10)
    np.testing.assert_allclose(beta / np.sqrt(np.diag(cov)), fit.tvalues[:2], rtol=1e-10)


def test_webb_enumeration():
    assert h2.WEBB == (-math.sqrt(1.5), -1.0, -math.sqrt(0.5), math.sqrt(0.5), 1.0,
                       math.sqrt(1.5))
    v = h2.webb_vectors(4)
    assert v.shape == (1296, 4)
    assert len({tuple(row) for row in v}) == 1296
    rng = np.random.default_rng(SEED)
    df = h2_frame(rng.normal(size=20), {r: rng.normal(size=20) for r in R2_R5})
    p, n = h2.wild_bootstrap_p(df, "automation_pct")
    assert n == 1296 and 0 < p <= 1


def test_h2_recovers_planted_trend():
    rng = np.random.default_rng(SEED)
    n = 500
    alpha = rng.normal(0, 5, n)
    df = h2_frame(alpha, {r: 3 * H2_TIMES[r] + rng.normal(0, 0.5, n) for r in R2_R5})
    res = h2.estimate_h2(df)
    tr = res.coefs["trend"]
    assert abs(tr.estimate - 3) < 0.3 and tr.p < 1e-6
    assert tr.df == n - 1 and tr.ci_low < tr.estimate < tr.ci_high
    assert res.p_family == tr.p
    assert res.hypothesis == "H2" and res.outcome == "automation_pct"
    assert res.sample["n_tasks"] == n and res.sample["n_rows"] == 4 * n
    assert res.sample["releases"] == list(R2_R5)
    assert res.sample["times"] == pytest.approx(H2_TIMES)
    assert res.diagnostics["n_wild_draws"] == 1296
    assert set(res.diagnostics["release_effects"]) == {"r3", "r4", "r5"}
    notes = " ".join(res.notes)
    assert "With four clusters the release-level co-condition is demanding and may be " \
           "conservative" in notes
    assert "measured within-task automation" in notes
    assert "includes any change in the classifier and in platform scope" in notes
    assert "descriptive only; smallest attainable p = 1/24" in notes
    res.to_dict()  # JSON-safe


def test_wild_bootstrap_controls_release_shocks():
    n_task, reps = 200, 100
    wild_hits = clustered_hits = 0
    for i in range(reps):
        rng = np.random.default_rng(SEED + i)
        alpha = rng.normal(0, 1, n_task)
        shock = rng.normal(0, 2, 4)
        eps = rng.normal(0, 1, (4, n_task))
        df = h2_frame(alpha, {r: shock[j] + eps[j] for j, r in enumerate(R2_R5)})
        assert df["weight"].unique().to_list() == [1.0]
        res = h2.estimate_h2(df)
        assert res.diagnostics["n_wild_draws"] == 1296
        wild_hits += res.diagnostics["p_wild"] <= 0.0125
        clustered_hits += res.p_family <= 0.0125
    print(f"share p_wild <= 0.0125: {wild_hits / reps}; "
          f"share task-clustered p <= 0.0125: {clustered_hits / reps}")
    assert wild_hits / reps <= 0.05
    assert clustered_hits / reps >= 0.30


def test_wild_bootstrap_has_power_and_a_floor():
    """A strong trend with no release shocks gives a small p_wild, but never below 6/1296:
    the six constant Webb vectors reproduce |t| exactly (the statistic is scale-invariant)."""
    rng = np.random.default_rng(SEED)
    n = 500
    df = h2_frame(rng.normal(0, 5, n), {r: 3 * H2_TIMES[r] + rng.normal(0, 0.5, n)
                                        for r in R2_R5})
    p, n_draws = h2.wild_bootstrap_p(df, "automation_pct")
    assert 6 / 1296 <= p <= 0.05 and n_draws == 1296


def test_release_label_p_floor():
    rng = np.random.default_rng(SEED)
    n = 100
    df = h2_frame(rng.normal(0, 5, n), {r: 3 * H2_TIMES[r] + rng.normal(0, 0.01, n)
                                        for r in R2_R5})
    assert h2.release_label_p(df, "automation_pct") == pytest.approx(1 / 24)
    assert h2.estimate_h2(df).diagnostics["p_release_label"] == pytest.approx(1 / 24)


def test_release_effects_base_r2():
    rng = np.random.default_rng(SEED)
    n = 100
    delta = dict(zip(R2_R5, (0.0, 1.0, 2.0, 4.0), strict=True))
    df = h2_frame(rng.normal(0, 5, n), {r: delta[r] + rng.normal(0, 0.01, n) for r in R2_R5})
    eff = h2.release_effects(df, "automation_pct")
    assert set(eff) == {"r3", "r4", "r5"}
    for r in ("r3", "r4", "r5"):
        assert eff[r].estimate == pytest.approx(delta[r], abs=0.05)
        assert eff[r].ci_low < eff[r].estimate < eff[r].ci_high and eff[r].df == n - 1


def test_outcome_and_knobs(fixture_panel):
    rels = ("r2", "r3", "r4", "r5", "r6")
    df = h2.build_h2_panel(fixture_panel, outcome="validation_pct", balanced=False,
                           releases=rels)
    assert df.columns == ["task_node", "release", "t", "validation_pct", "weight"]
    # T2 in r6: May only, averaged over the month that has it (D13), never 0.
    t2r6 = df.filter((pl.col("task_node") == "T2") & (pl.col("release") == "r6"))
    assert t2r6["validation_pct"].item() == pytest.approx(28.0)
    res = h2.estimate_h2(df, "validation_pct", r6_indicator=True)
    assert "trend" in res.coefs and "r6" in res.coefs
    assert res.diagnostics["n_wild_draws"] == 6**5
    assert res.outcome == "validation_pct"
    assert any("smallest attainable p = 1/120" in n for n in res.notes)


def test_r6_indicator_requires_r6():
    rng = np.random.default_rng(SEED)
    df = h2_frame(rng.normal(size=10), {r: rng.normal(size=10) for r in R2_R5})
    with pytest.raises(ValueError, match="r6"):
        h2.estimate_h2(df, r6_indicator=True)
