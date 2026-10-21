from pathlib import Path

import polars as pl
import pytest

from aideleg.aei import schema
from aideleg.aei.parse_early import parse_r1, parse_r2
from aideleg.aei.tasks import TaskIndex

FIX = Path(__file__).parent.parent / "fixtures" / "aei"


@pytest.fixture
def index(tmp_path: Path) -> TaskIndex:
    p = tmp_path / "onet.csv"
    pl.DataFrame({
        "O*NET-SOC Code": ["11-1011.00", "13-1011.00"],
        "Title": ["t", "t"],
        "Task ID": [101, 202],
        "Task": ["Act as advisers to student organizations.", "Write reports"],
        "Task Type": ["Core", "Core"],
    }).write_csv(p)
    return TaskIndex.from_onet(p)


@pytest.fixture
def r1(index, tmp_path):
    d = tmp_path / "r1"
    d.mkdir()
    (d / "onet_task_mappings.csv").write_text((FIX / "r1_task_pct_small.csv").read_text())
    (d / "automation_vs_augmentation.csv").write_text((FIX / "r1_collab_small.csv").read_text())
    return d


@pytest.fixture
def r2(tmp_path):
    d = tmp_path / "r2"
    d.mkdir()
    (d / "task_pct_v2.csv").write_text((FIX / "r2_task_pct_small.csv").read_text())
    by_task = d / "automation_vs_augmentation_by_task.csv"
    by_task.write_text((FIX / "r2_collab_small.csv").read_text())
    return d


def _v(df, node, metric):
    r = df.filter((pl.col("node_name") == node) & (pl.col("metric") == metric))
    assert r.height == 1, (node, metric, r.height)
    return r["value"][0]


T = "act as advisers to student organizations."


def test_r2_pattern_shares_renormalise(r2, index):
    df = parse_r2(r2, index)
    assert _v(df, T, "directive_pct") == pytest.approx(51.43, abs=0.01)
    assert _v(df, T, "task_iteration_pct") == pytest.approx(48.57, abs=0.01)
    assert _v(df, T, "automation_pct") == pytest.approx(51.43, abs=0.01)
    assert _v(df, T, "augmentation_pct") == pytest.approx(48.57, abs=0.01)
    assert _v(df, T, "filtered_pct") == pytest.approx(25.53, abs=0.01)


def test_r2_fully_filtered_task_is_null(r2, index):
    df = parse_r2(r2, index)
    for m in ["feedback_loop_pct", "directive_pct", "task_iteration_pct", "validation_pct",
              "learning_pct", "automation_pct", "augmentation_pct"]:
        assert _v(df, "write reports.", m) is None
    assert _v(df, "write reports.", "filtered_pct") == pytest.approx(100.0)


def test_r1_pct_kept_in_percent(r1, index):
    df = parse_r1(r1, index)
    # published pct is already percent (the real file sums to 100): 0.006775 stays 0.006775
    assert _v(df, T, "pct") == pytest.approx(0.006775)


def test_task_pct_sums_to_100(r1, r2, index):
    for df in (parse_r1(r1, index), parse_r2(r2, index)):
        pct = df.filter((pl.col("taxonomy") == "onet_task") & (pl.col("metric") == "pct"))
        s = pct["value"].sum()
        assert s == pytest.approx(100.0, abs=0.01)


def test_outputs_conform_to_schema(r1, r2, index):
    for df in (parse_r1(r1, index), parse_r2(r2, index)):
        assert df.columns == schema.PANEL_COLUMNS
        assert all(schema.is_canonical(m) for m in df["metric"].unique())
        assert set(df["taxonomy"].unique()) <= schema.TAXONOMIES
        assert df["geo_id"].unique().to_list() == ["GLOBAL"]
        assert df["geo_level"].unique().to_list() == ["global"]
        assert df["source"].unique().to_list() == ["claude_ai"]


def test_node_ids_and_unmatched(r1, r2, index):
    d1, d2 = parse_r1(r1, index), parse_r2(r2, index)
    for df in (d1, d2):
        assert _v(df.filter(pl.col("node_id") == "101"), T, "pct") is not None
        unk = df.filter(pl.col("node_name") == "unknown task text.")["node_id"][0]
        assert unk == "unmatched:unknown task text"
    # sentinel row stays so pct sums to 100
    assert d1.filter(pl.col("node_name") == "none")["node_id"][0] == "unmatched:none"
    # whitespace/case drift still matches
    assert d1.filter(pl.col("node_name") == "Write   Reports.")["node_id"][0] == "202"


def test_release_metadata(r1, r2, index):
    d1, d2 = parse_r1(r1, index), parse_r2(r2, index)
    assert d1["release"].unique().to_list() == ["r1"]
    assert d2["release"].unique().to_list() == ["r2"]
    assert d1["definition"].unique().to_list() == ["collab_v1"]
    assert d2["definition"].unique().to_list() == ["collab_v2"]
    assert d2["period_start"][0].isoformat() == "2025-02-24"


def test_r1_overall_collab(r1, index):
    df = parse_r1(r1, index).filter(pl.col("taxonomy") == "overall")
    assert _v(df, "overall", "feedback_loop_pct") == pytest.approx(10 / 90 * 100)
    assert _v(df, "overall", "automation_pct") == pytest.approx(30 / 90 * 100)
    assert _v(df, "overall", "augmentation_pct") == pytest.approx(60 / 90 * 100)
    assert _v(df, "overall", "none_pct") == pytest.approx(5.0)
