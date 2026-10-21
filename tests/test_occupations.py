from datetime import date

import polars as pl
import pytest

from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.aei.tasks import TaskIndex
from aideleg.config import DERIVED, RAW
from aideleg.occupations import occupation_table, soc_rollup, unallocated_mass

P0, P1 = date(2025, 8, 4), date(2025, 8, 11)


def _panel(rows, release="r3", source="claude_ai", taxonomy="onet_task", start=P0):
    """rows: (node_id, node_name, metric, value)."""
    return pl.DataFrame(
        {
            "release": [release] * len(rows),
            "period_start": [start] * len(rows),
            "period_end": [P1] * len(rows),
            "source": [source] * len(rows),
            "geo_level": ["global"] * len(rows),
            "geo_id": ["GLOBAL"] * len(rows),
            "taxonomy": [taxonomy] * len(rows),
            "level": [0] * len(rows),
            "node_id": [r[0] for r in rows],
            "node_name": [r[1] for r in rows],
            "metric": [r[2] for r in rows],
            "value": [float(r[3]) for r in rows],
            "definition": ["collab_v2"] * len(rows),
        },
        schema={c: (pl.Date if c.startswith("period") else pl.Int64 if c == "level"
                    else pl.Float64 if c == "value" else pl.String) for c in PANEL_COLUMNS},
    )


# task text -> ids, id -> O*NET-SOC 2019 codes
INDEX = TaskIndex(
    {"write code": [1], "review code": [2], "plan budgets": [3, 4], "teach": [5]},
    {1: ["15-1252.00"], 2: ["15-1252.00", "15-1253.00"], 3: ["13-2011.00"],
     4: ["11-3031.01"], 5: ["25-1021.00"]},
)


def _row(t, soc):
    return t.filter(pl.col("soc6") == soc).row(0, named=True)


def test_equal_allocation_conserves_usage():
    panel = _panel([
        ("1", "write code", "pct", 3), ("2", "review code", "pct", 1),
        ("3", "plan budgets", "pct", 2), ("unmatched:none", "none", "pct", 4),
    ])
    t = occupation_table(panel, "r3", INDEX)
    assert t["usage_share"].sum() == pytest.approx(6.0)
    assert _row(t, "15-1253")["usage_share"] == pytest.approx(0.5)
    # "plan budgets" carries IDs 3 and 4: the union of their occupations shares it
    assert _row(t, "13-2011")["usage_share"] == pytest.approx(1.0)
    assert _row(t, "11-3031")["usage_share"] == pytest.approx(1.0)
    un = unallocated_mass(panel, "r3", INDEX)
    assert un.row(0, named=True)["pct"] == pytest.approx(4.0)


def test_full_allocation_gives_each_occupation_full_pct():
    panel = _panel([("2", "review code", "pct", 1)])
    t = occupation_table(panel, "r3", INDEX, allocation="full")
    assert t["usage_share"].to_list() == [1.0, 1.0]


def test_weighted_pattern_mean():
    panel = _panel([
        ("1", "write code", "pct", 3), ("1", "write code", "automation_pct", 60),
        ("9", "write code", "pct", 1), ("9", "write code", "automation_pct", 20),
    ])
    t = occupation_table(panel, "r3", INDEX)
    r = _row(t, "15-1252")
    assert r["automation_pct"] == pytest.approx(50.0)
    assert r["n_tasks"] == 2


def test_null_pattern_tasks_excluded_from_mean():
    panel = _panel([
        ("1", "write code", "pct", 3), ("1", "write code", "automation_pct", 60),
        ("9", "write code", "pct", 1), ("9", "write code", "automation_pct", 20),
        ("8", "write code", "pct", 10),  # automation unpublished
    ])
    r = _row(occupation_table(panel, "r3", INDEX), "15-1252")
    assert r["automation_pct"] == pytest.approx(50.0)
    assert r["usage_share"] == pytest.approx(14.0)
    assert r["directive_pct"] is None


def test_suppression_bounds_r3():
    panel = _panel([
        ("1", "write code", "pct", 1), ("1", "write code", "automation_pct", 80),
        ("1", "write code", "none_pct", 5), ("1", "write code", "not_classified_pct", 15),
    ])
    r = _row(occupation_table(panel, "r3", INDEX), "15-1252")
    assert r["suppressed_pct"] == pytest.approx(20.0)
    assert r["automation_share_all_lb"] == pytest.approx(64.0)
    assert r["automation_share_all_ub"] == pytest.approx(84.0)


def test_suppression_bounds_aggregate_task_level_values():
    panel = _panel([
        ("1", "write code", "pct", 3), ("1", "write code", "automation_pct", 100),
        ("1", "write code", "filtered_pct", 0),
        ("9", "write code", "pct", 1), ("9", "write code", "automation_pct", 0),
        ("9", "write code", "filtered_pct", 100),
    ], release="r2")
    r = _row(occupation_table(panel, "r2", INDEX), "15-1252")
    assert r["suppressed_pct"] == pytest.approx(25.0)
    assert r["automation_share_all_lb"] == pytest.approx(75.0)  # (3*100 + 1*0) / 4
    assert r["automation_share_all_ub"] == pytest.approx(100.0)  # (3*100 + 1*100) / 4


def test_r1_has_no_suppression_measure():
    panel = _panel([("1", "write code", "pct", 1)], release="r1")
    r = _row(occupation_table(panel, "r1", INDEX), "15-1252")
    assert r["suppressed_pct"] is None and r["automation_share_all_lb"] is None


def test_table_keyed_by_period_and_source():
    panel = pl.concat([
        _panel([("1", "write code", "pct", 1)], release="r6"),
        _panel([("1", "write code", "pct", 2)], release="r6", source="1p_api"),
        _panel([("1", "write code", "pct", 4)], release="r6", start=P1),
    ])
    t = occupation_table(panel, "r6", INDEX, basis="tasks")
    assert t.height == 3
    assert t.select("period_start", "source", "soc6").is_unique().all()
    assert sorted(t["usage_share"].to_list()) == [1.0, 2.0, 4.0]


def test_r6_default_uses_published_soc_rows():
    tasks = _panel([("1", "write code", "pct", 9)], release="r6")
    soc = _panel([
        ("15-1252.00", "Software Developers", "pct", 3),
        ("15-1252.00", "Software Developers", "automation_pct", 60),
        ("15-1252.01", "x", "pct", 1), ("15-1252.01", "x", "automation_pct", 20),
    ], release="r6", taxonomy="soc_detailed")
    t = occupation_table(pl.concat([tasks, soc]), "r6", INDEX)
    r = _row(t, "15-1252")
    assert t["basis"].unique().to_list() == ["published"]
    assert r["usage_share"] == pytest.approx(4.0)
    assert r["automation_pct"] == pytest.approx(50.0)
    t2 = occupation_table(pl.concat([tasks, soc]), "r6", INDEX, basis="tasks")
    assert _row(t2, "15-1252")["usage_share"] == pytest.approx(9.0)


def test_only_global_rows_used():
    panel = _panel([("1", "write code", "pct", 3)])
    country = panel.with_columns(geo_level=pl.lit("country"), geo_id=pl.lit("US"))
    t = occupation_table(pl.concat([panel, country]), "r3", INDEX)
    assert t["usage_share"].sum() == pytest.approx(3.0)


def test_null_node_name_still_allocated_by_node_id():
    panel = _panel([("1", None, "pct", 2)])
    t = occupation_table(panel, "r3", INDEX)
    assert _row(t, "15-1252")["usage_share"] == pytest.approx(2.0)
    assert unallocated_mass(panel, "r3", INDEX).is_empty()


def test_soc_rollup_matches_oews_aggregates():
    assert soc_rollup("15-1252", {"15-1250"}) == "15-1250"
    assert soc_rollup("15-1252", {"15-1252"}) == "15-1252"
    assert soc_rollup("15-1252", {"15-1252", "15-1250"}) == "15-1252"
    assert soc_rollup("29-1229", {"15-1250"}) == "29-1229"


# --- real data -----------------------------------------------------------------------

PANEL_PATH = DERIVED / "aei_panel.parquet"


@pytest.mark.data
@pytest.mark.skipif(not RAW.exists() or not PANEL_PATH.exists(),
                    reason="needs data/raw and `make panel`")
def test_r6_task_allocation_close_to_published_soc():
    from aideleg.aei.tasks import default_index

    panel = pl.read_parquet(PANEL_PATH).filter(pl.col("release") == "r6")
    idx = default_index()
    pub = occupation_table(panel, "r6", idx, basis="published")
    alloc = occupation_table(panel, "r6", idx, basis="tasks")
    key = ["period_start", "source", "soc6"]
    j = pub.select(*key, pub=pl.col("usage_share")).join(
        alloc.select(*key, alloc=pl.col("usage_share")), on=key, how="inner")
    rho = j.group_by("period_start", "source").agg(
        rho=pl.corr("pub", "alloc", method="spearman"), n=pl.len()).sort("period_start", "source")
    assert rho.height == 4, rho
    assert rho["rho"].min() >= 0.9, rho
