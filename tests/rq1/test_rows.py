import math
from datetime import date

import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex
from aideleg.config import DERIVED, RAW
from aideleg.rq1 import rows as R

APR, MAY = date(2026, 4, 1), date(2026, 5, 1)
A, B, C, T, X = "11-1011", "13-2011", "23-1011", "25-1021", "99-9999"


def _panel(nodes, release="r6", source="claude_ai"):
    """nodes: (node_id, node_name, period_start, {metric: value})."""
    recs = [(release, p, p, source, "global", "GLOBAL", "onet_task", 0, nid, name, m, float(v),
             "collab_v2") for nid, name, p, ms in nodes for m, v in ms.items()]
    schema = {c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                  else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS}
    return pl.DataFrame(recs, schema=schema, orient="row")


def _both(nid, name, **ms):
    return [(nid, name, APR, ms), (nid, name, MAY, ms)]


@pytest.fixture
def index(tmp_path):
    rows = [(f"{A}.00", 1, "Plan budgets."), (f"{B}.00", 2, "Plan budgets."),
            (f"{A}.00", 3, "Write code."), (f"{B}.00", 3, "Write code."),
            (f"{C}.00", 3, "Write code."), (f"{T}.00", 4, "Teach."), (f"{X}.00", 5, "Lone.")]
    f = tmp_path / "tasks.txt"
    f.write_text("O*NET-SOC Code\tTask ID\tTask\tTask Type\tIncumbents Responding\tDate\t"
                 "Domain Source\r\n" + "".join(f"{c}\t{i}\t{t}\tCore\t1\t1\tA\r\n"
                                                for c, i, t in rows), encoding="utf-8")
    return TaskIndex.from_onet(f)


FAMILIES = pl.DataFrame({"task_id": [1, 2, 3, 3, 5], "family": ["f1", "f2", "f1", "f2", "f1"]},
                        schema={"task_id": pl.Int64, "family": pl.String})
WAGES = pl.DataFrame({"soc6": [A, B, C, T], "tot_emp": [10, 20, 30, 40],
                      "a_median": [100000.0, 239200.0, 80000.0, None],
                      "a_median_status": ["published", "topcoded", "published", "suppressed"]})
OEWS = {A, B, C, T}
VALS = dict(automation_pct=50.0, augmentation_pct=50.0, directive_pct=30.0,
            feedback_loop_pct=20.0, task_iteration_pct=20.0, validation_pct=20.0,
            learning_pct=10.0, ai_autonomy_mean=3.0, human_education_years_mean=14.0,
            none_pct=10.0)


def _build(panel, index, **kw):
    return R.build_task_rows(panel, index, FAMILIES, WAGES, OEWS, None, **kw)


def test_weights_conserve_usage(index):
    out = _build(_panel(_both("3", "Write code", pct=6.0, **VALS)), index)
    r = out.rows
    assert r.height == 6
    assert r["weight"].to_list() == [pytest.approx(1.0)] * 6
    assert r["n_occ"].unique().to_list() == [3] and r["n_family"].unique().to_list() == [2]
    assert sorted(set(r["soc6"])) == [A, B, C] and sorted(set(r["family"])) == ["f1", "f2"]
    assert r["weight"].sum() == pytest.approx(out.total_weight) == pytest.approx(6.0)


def test_structural_drop_shares(index):
    panel = _panel(_both("3", "Write code", pct=6.0, **VALS)
                   + _both("unmatched:none", "none", pct=2.0)
                   + _both("4", "Teach", pct=1.0, **VALS)
                   + _both("1", "Plan budgets", pct=1.0, **VALS)
                   + _both("5", "Lone", pct=0.0, **VALS))
    out = _build(panel, index)
    assert out.total_weight == pytest.approx(10.0)
    d = out.structural_drops
    assert list(d) == ["unmatched_task", "no_occupation", "no_family", "zero_weight"]
    assert d["unmatched_task"] == pytest.approx(20.0)
    assert d["no_family"] == pytest.approx(10.0)
    assert d["no_occupation"] == 0.0 and d["zero_weight"] == 0.0
    assert set(out.rows["task_node"]) == {"3", "1"}
    assert (out.release, out.source, out.family_level) == ("r6", "claude_ai", "iwa")


def test_no_occupation_drop(index):
    panel = _panel(_both("3", "Write code", pct=3.0, **VALS)
                   + _both("777", "Not in the index", pct=1.0, **VALS))
    out = _build(panel, index)
    assert out.structural_drops["no_occupation"] == pytest.approx(25.0)


def test_wage_status_no_oews_code_kept_as_row(index):
    out = _build(_panel(_both("5", "Lone", pct=1.0, **VALS)), index)
    r = out.rows.row(0, named=True)
    assert out.rows.height == 1
    assert r["soc6"] == X and r["oews_code"] is None
    assert r["wage_status"] == "no_oews_code" and r["log_wage"] is None


def test_topcoded_wage_log(index):
    out = _build(_panel(_both("2", "Plan budgets", pct=1.0, **VALS)), index)
    r = out.rows.filter(pl.col("soc6") == B).row(0, named=True)
    assert r["wage_status"] == "topcoded"
    assert r["log_wage"] == pytest.approx(math.log(239200.0))
    assert r["error_cost"] == 1
    assert out.rows.filter(pl.col("soc6") == A)["error_cost"].unique().to_list() == [0]


def test_bounds_computed_per_period_then_averaged(index):
    v = {k: x for k, x in VALS.items() if k not in ("automation_pct", "none_pct")}
    panel = _panel([("1", "Plan budgets", APR, dict(pct=1.0, automation_pct=60.0,
                                                    none_pct=10.0, **v)),
                    ("1", "Plan budgets", MAY, dict(pct=1.0, automation_pct=40.0,
                                                    none_pct=30.0, **v))])
    r = _build(panel, index).rows.row(0, named=True)
    assert r["automation_pct"] == pytest.approx(50.0)
    assert r["automation_share_all_lb"] == pytest.approx(41.0)
    assert r["automation_share_all_ub"] == pytest.approx(61.0)  # mean(54 + 10, 28 + 30)


def test_one_month_unpublished_is_skipped_not_zero(index):
    panel = _panel([("3", "Write code", APR, dict(pct=4.0, **VALS)),
                    ("1", "Plan budgets", APR, dict(pct=2.0, **VALS)),
                    ("1", "Plan budgets", MAY, dict(pct=2.0, **{**VALS, "automation_pct": 10.0}))])
    out = _build(panel, index)
    w = out.rows.group_by("task_node").agg(pl.col("weight").sum(), pl.col("automation_pct").first())
    w = dict(zip(w["task_node"], w.select("weight", "automation_pct").rows(), strict=True))
    assert w["3"] == (pytest.approx(2.0), pytest.approx(50.0))  # May unpublished: not 0
    assert w["1"] == (pytest.approx(2.0), pytest.approx(30.0))


def test_union_of_candidate_ids(index):
    # "Plan budgets" carries ID 1 (occupation A, family f1) and ID 2 (occupation B, family f2)
    out = _build(_panel(_both("1", "Plan budgets", pct=4.0, **VALS)), index)
    r = out.rows
    assert sorted(set(r["soc6"])) == [A, B] and sorted(set(r["family"])) == ["f1", "f2"]
    assert r.height == 4 and r["weight"].to_list() == [pytest.approx(1.0)] * 4


def test_columns_and_codes(index):
    panel = _panel(_both("3", "Write code", pct=6.0, **VALS)
                   + _both("1", "Plan budgets", pct=1.0, **VALS))
    r = _build(panel, index).rows
    assert r.columns == R.ROW_COLUMNS
    assert R.ROW_COLUMNS[-4:] == ["human_education_years_mean", "log_wage", "wage_status",
                                  "error_cost"]
    assert sorted(set(r["occ_code"])) == [0, 1, 2]
    assert sorted(set(r["task_code"])) == [0, 1]
    assert r.schema["occ_code"] == pl.Int64 and r.schema["task_code"] == pl.Int64
    codes = r.select("soc6", "occ_code").unique().sort("soc6")
    assert codes["occ_code"].to_list() == [0, 1, 2]
    tasks = r.select("task_node", "task_code").unique().sort("task_node")
    assert tasks.to_dicts() == [{"task_node": "1", "task_code": 0},
                                {"task_node": "3", "task_code": 1}]


def test_other_release_and_source_ignored(index):
    panel = pl.concat([_panel(_both("3", "Write code", pct=6.0, **VALS)),
                       _panel(_both("1", "Plan budgets", pct=9.0, **VALS), source="1p_api"),
                       _panel(_both("1", "Plan budgets", pct=9.0, **VALS), release="r5")])
    out = _build(panel, index)
    assert out.total_weight == pytest.approx(6.0)
    assert set(out.rows["task_node"]) == {"3"}


_PANEL = DERIVED / "aei_panel.parquet"


@pytest.mark.data
@pytest.mark.skipif(not _PANEL.exists() or not (RAW / "onet").exists(),
                    reason="needs the panel and O*NET files")
def test_real_rows_coverage():
    """Coverage only: sample sizes and drop shares. No outcome column is printed."""
    from aideleg.acquire.sources import by_key
    from aideleg.aei.tasks import default_index
    from aideleg.bls.oews import load_national_wages
    from aideleg.rq1.inputs import task_families

    try:
        wages = load_national_wages(2024)
    except FileNotFoundError:
        pytest.skip("OEWS 2024 not downloaded")
    struct = pl.read_csv(RAW / by_key("aei_soc_structure").dest)
    out = R.build_task_rows(pl.read_parquet(_PANEL), default_index(), task_families("iwa"),
                            wages, set(wages["soc6"]), struct)
    r = out.rows
    print(f"\ntotal_weight: {out.total_weight:.4f}")
    print(f"structural_drops (% of total_weight): {out.structural_drops}")
    print(f"rows: {r.height}; tasks: {r['task_node'].n_unique()}; soc6: {r['soc6'].n_unique()}; "
          f"families: {r['family'].n_unique()}")
    assert sum(out.structural_drops.values()) < 15.0
