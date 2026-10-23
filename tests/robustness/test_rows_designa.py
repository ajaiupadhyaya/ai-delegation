"""Plan 4 Task 10: the Design A and event rows R4, R8, R9 and R16, on stubbed Plan 3 runners
(no market data)."""

from datetime import date

import polars as pl
import pytest

from aideleg.robustness import report, rows, upstream
from aideleg.robustness.exposure_variants import OUT_COLUMNS
from aideleg.robustness.upstream import AEI_COLS, BENCH_COLS

NAMES = [f"I{i:02d}" for i in range(1, 50)]
PATTERNS = ["directive_pct", "automation_pct"]


def _fake_variant(spec):
    n = len(NAMES)
    data = {
        "industry": list(range(1, n + 1)),
        "industry_short": NAMES,
        **{c: [float(k % 7) - 3.0 for k in range(n)] for c in OUT_COLUMNS[2:]},
    }
    return pl.DataFrame(data).select(OUT_COLUMNS)


def _fake_primary():
    frames = []
    for d in ("B", "A_r2", "A_pooled"):
        frames.append(
            pl.DataFrame(
                {
                    "design": [d] * len(NAMES),
                    "ff49": list(range(1, len(NAMES) + 1)),
                    "ff49_short": NAMES,
                    "z_delegation": [float(k % 5) for k in range(len(NAMES))],
                    "z_usage": [0.0] * len(NAMES),
                    "z_aioe": [1.0] * len(NAMES),
                }
            )
        )
    return pl.concat(frames)


def _fake_zero():
    return pl.DataFrame({"design": ["B", "A_r2", "A_pooled"], "no_usage_emp_pct": [1.5, 1.5, 2.25]})


def _fake_rq2(exposure, bench):
    return pl.DataFrame(
        [
            {
                "aei": a,
                "benchmark": b,
                "n": exposure.height,
                "spearman": 0.5,
                "ci_low": 0.2,
                "ci_high": 0.7,
                "n_draws_used": 10_000,
            }
            for a in AEI_COLS
            for b in BENCH_COLS
        ]
    )


def _designs(expo):
    return [d for d in ("A_r2", "A_pooled") if d in set(expo["design"].to_list())]


@pytest.fixture
def stubbed(monkeypatch, tmp_path):
    calls: dict[str, list[dict]] = {"terciles": [], "fm": [], "events": [], "decile": []}

    def fake_terciles(out_dir, months=None, expo=None, *, fig_dir=None):
        assert fig_dir is None
        calls["terciles"].append({"out_dir": out_dir, "months": months, "expo": expo})
        recs = [
            {
                "design": d,
                "weighting": w,
                "statistic": s,
                "estimate": 1.0,
                "se": 0.5,
                "ci_lo": 0.0,
                "ci_hi": 2.0,
                "p": 0.2,
                "T": 45,
            }
            for d in _designs(expo)
            for w in ("cap", "ew")
            for s in ("alpha_CAPM", "mean", "sharpe")
        ]
        return pl.DataFrame(recs)

    def fake_fm(out_dir, months=None, expo=None):
        calls["fm"].append({"out_dir": out_dir, "months": months, "expo": expo})
        recs = [
            {
                "design": d,
                "window": "A",
                "regressor": r,
                "mean": 0.1,
                "se": 0.05,
                "ci_lo": 0.0,
                "ci_hi": 0.2,
                "p": 0.04,
                "T": 45,
                "n_mean": 47.0,
                "skipped": 0,
            }
            for d in _designs(expo)
            for r in ("z", "log_size")
        ]
        return pl.DataFrame(recs)

    def fake_events(out_dir, events=upstream.EVENTS, expo=None, *, fig_dir=None):
        assert fig_dir is None
        calls["events"].append({"out_dir": out_dir, "events": tuple(events), "expo": expo})
        recs = []
        for k, e in enumerate(events):
            for h in (5, 20):
                for d in _designs(expo):
                    recs.append(
                        {
                            "event": e.name,
                            "day0": e.announced,
                            "horizon": h,
                            "design": d,
                            "regressors": "z_delegation",
                            "regressor": "z_delegation",
                            "b": float(k % 9) - 4.0 + h / 100,
                            "se": 0.3,
                            "ci_lo": -1.0,
                            "ci_hi": 1.0,
                            "p": 0.5,
                            "n": 48,
                        }
                    )
        return pl.DataFrame(recs)

    def fake_decile(
        panel, index, wages, national, soc, *, release="r6", source="claude_ai", basis="published"
    ):
        calls["decile"].append({"basis": basis, "release": release, "source": source})
        v = 10.0 if basis == "tasks" else 20.0
        return pl.DataFrame(
            {
                "decile": [1, 2, None],
                "emp_share": [50.0, 50.0, 0.0],
                "usage_share": [60.0, 40.0, 0.0],
                "n_occ": [3, 4, 0],
                **{c: [v, v + 1, None] for c in PATTERNS},
            }
        )

    monkeypatch.setattr(upstream, "run_terciles", fake_terciles)
    monkeypatch.setattr(upstream, "run_fm", fake_fm)
    monkeypatch.setattr(upstream, "run_events", fake_events)
    monkeypatch.setattr(upstream, "exposures", _fake_primary)
    monkeypatch.setattr(upstream, "zero_assigned", _fake_zero)
    monkeypatch.setattr(upstream, "by_wage_decile", fake_decile)
    monkeypatch.setattr(rows, "variant_exposure", _fake_variant)
    monkeypatch.setattr(rows, "rq2_correlations", _fake_rq2)
    monkeypatch.setattr(rows, "zero_assigned_share", lambda spec: 12.345)
    monkeypatch.setattr(rows, "_r6_inputs", lambda: (None, None, None, None, None))
    monkeypatch.setattr(rows, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(rows, "WORK_DIR", tmp_path / "work")
    (tmp_path / "out").mkdir()
    return calls


def _run(row_id):
    csv, md = rows.RUNNERS[row_id]()
    return pl.read_csv(csv, infer_schema_length=None), md.read_text(encoding="utf-8")


# --- R9 placebo dates and R8 months (no stubs needed) -------------------------------------


def test_r9_placebo_dates():
    ev = rows.placebo_events()
    assert len(ev) == 56
    dates = {e.announced for e in ev}
    assert all(d.year != 2020 for d in dates)
    assert {d.year for d in dates} == {2017, 2018, 2019, 2021}
    assert date(2017, 11, 30) in dates and date(2021, 3, 14) in dates
    md = {(e.announced.month, e.announced.day) for e in upstream.EVENTS}
    assert all((d.month, d.day) in md for d in dates)
    assert len({e.name for e in ev}) == 56
    assert all(" placebo " in e.name for e in ev)


def test_r9_no_placebo_named_chatgpt():
    from aideleg.rq3.events import ESZ_EVENT

    assert ESZ_EVENT not in {e.name for e in rows.placebo_events()}


def test_r8_months_exclude_only_2023():
    m = rows.months_without_2023()
    assert set(m) == {"A"}
    a = m["A"]
    assert len(a) == 33
    assert all(d.year != 2023 for d in a)
    assert date(2022, 12, 31) in a and date(2024, 1, 31) in a
    assert date(2026, 8, 31) in a
    assert a == sorted(a)


# --- R8 -------------------------------------------------------------------------------------


def test_r8_passes_months_to_terciles_and_fm(stubbed):
    df, md = _run("R8")
    assert len(stubbed["terciles"]) == 1 and len(stubbed["fm"]) == 1
    assert stubbed["events"] == []
    for c in (stubbed["terciles"][0], stubbed["fm"][0]):
        assert c["months"] == rows.months_without_2023()
        assert set(c["expo"]["design"].to_list()) == {"A_r2", "A_pooled"}
    assert stubbed["terciles"][0]["out_dir"] == rows.WORK_DIR / "R8" / "terciles"
    assert stubbed["fm"][0]["out_dir"] == rows.WORK_DIR / "R8" / "fm"
    assert set(df["part"]) == {"terciles", "fm"}
    assert set(df["label"]) == {"robustness; exploratory"}
    assert "Zero-assigned employment share, Design A_r2: 1.50% (D3)" in md
    assert "Zero-assigned employment share, Design A_pooled: 2.25% (D3)" in md
    assert "C-37" in md
    assert "DSR here is against the 4 tercile variants run in this row" in md
    terc = df.filter(pl.col("part") == "terciles")
    assert all("C-37" in n for n in terc["note"])


# --- R4 and R16 -----------------------------------------------------------------------------


def test_r4_requires_api_pool(stubbed, monkeypatch):
    seen = []
    monkeypatch.setattr(
        rows, "variant_exposure", lambda spec: (seen.append(spec), _fake_variant(spec))[1]
    )
    df, md = _run("R4")
    assert seen and all(s.source == "1p_api" and s.design == "A_pooled" for s in seen)
    for part in ("terciles", "fm", "events"):
        assert len(stubbed[part]) == 1
        c = stubbed[part][0]
        assert set(c["expo"]["design"].to_list()) == {"A_pooled"}
        assert c["out_dir"] == rows.WORK_DIR / "R4" / part
    assert stubbed["terciles"][0]["months"] is None
    assert set(df["part"]) == {"rq2", "index", "terciles", "fm", "events"}
    assert "Zero-assigned employment share (D3): 12.35%" in md
    assert "C-65" in md and "C-37" in md
    assert "DSR here is against the 2 tercile variants run in this row" in md
    terc = df.filter(pl.col("part") == "terciles")
    assert all("C-37" in n for n in terc["note"])
    assert set(terc["estimand"]) >= {"alpha_CAPM A_pooled cap", "sharpe A_pooled ew"}
    fm = df.filter(pl.col("part") == "fm")
    assert "FM z A_pooled" in set(fm["estimand"])
    ev = df.filter(pl.col("part") == "events")
    assert "CAR slope ChatGPT h5 A_pooled" in set(ev["estimand"])
    nulls = df.filter(pl.col("part").is_in(["terciles", "fm", "events"]))["null"]
    assert set(nulls.cast(pl.String).to_list()) == {"0"}


def test_r4_index_is_spearman_with_primary_a_pooled(stubbed):
    df, _ = _run("R4")
    idx = df.filter(pl.col("part") == "index")
    assert idx.height == 1
    r = idx.row(0, named=True)
    assert r["unit"] == report.RHO_UNIT and r["n"] == 49
    assert -1.0 <= r["estimate"] <= 1.0


def test_r16_descriptives_use_task_basis(stubbed):
    df, md = _run("R16")
    bases = [c["basis"] for c in stubbed["decile"]]
    assert sorted(bases) == ["published", "tasks"]
    assert all(c["release"] == "r6" and c["source"] == "claude_ai" for c in stubbed["decile"])
    desc = df.filter(pl.col("part") == "r6_descriptives")
    assert desc.height == 3 * len(PATTERNS)
    one = desc.filter(pl.col("estimand").str.contains("decile 1 directive_pct"))
    assert one["estimate"].to_list() == [10.0]
    assert one["note"].to_list()[0].startswith("published: 20.00")
    assert set(df["part"]) == {"rq2", "index", "terciles", "fm", "events", "r6_descriptives"}
    for part in ("terciles", "fm", "events"):
        assert set(stubbed[part][0]["expo"]["design"].to_list()) == {"A_pooled"}
    assert "Zero-assigned employment share (D3): 12.35%" in md


# --- R9 -------------------------------------------------------------------------------------


def test_r9_runs_placebo_and_actual_on_a_r2(stubbed):
    df, md = _run("R9")
    assert len(stubbed["events"]) == 2
    plc, act = stubbed["events"]
    assert plc["out_dir"] == rows.WORK_DIR / "R9"
    assert act["out_dir"] == rows.WORK_DIR / "R9_actual"
    assert plc["events"] == rows.placebo_events()
    assert act["events"] == tuple(upstream.EVENTS)
    for c in (plc, act):
        assert set(c["expo"]["design"].to_list()) == {"A_r2"}
    assert stubbed["terciles"] == [] and stubbed["fm"] == []
    slopes = df.filter(pl.col("part") == "placebo")
    assert slopes.height == 56 * 2
    assert all(e.startswith("CAR slope") for e in slopes["estimand"])
    assert set(df["applies_to"]) == {"event studies"}
    assert "C-76" in md
    summ = df.filter(pl.col("part") == "summary")
    assert summ.height == 2
    for r in summ.iter_rows(named=True):
        assert r["p"] is None
        assert 0.0 <= r["stat"] <= 100.0
        assert "descriptive" in r["note"]
    assert "not D19 events" in md and "C-60" in md
    assert "Zero-assigned employment share, Design A_r2: 1.50% (D3)" in md
    assert not (rows.WORK_DIR / "R9" / "eisfeldt_replication.md").exists()


def test_r9_percentile_definition():
    plc = [1.0, 2.0, 3.0, 4.0]
    assert rows.placebo_percentile(2.5, plc) == 50.0
    assert rows.placebo_percentile(0.0, plc) == 0.0
    assert rows.placebo_percentile(4.0, plc) == 100.0
