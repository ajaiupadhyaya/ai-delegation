from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg.aei import schema
from aideleg.aei.parse_r6 import parse_r6
from aideleg.aei.tasks import TaskIndex

FIX = Path(__file__).parent.parent / "fixtures" / "aei" / "r6_small.csv"
MAY = date(2026, 5, 1)


@pytest.fixture
def index(tmp_path: Path) -> TaskIndex:
    p = tmp_path / "onet.csv"
    pl.DataFrame({
        "O*NET-SOC Code": ["25-1011.00", "13-1011.00"],
        "Title": ["t", "t"],
        "Task ID": [101, 202],
        "Task": ["Act as advisers to student organizations.", "Write reports"],
        "Task Type": ["Core", "Core"],
    }).write_csv(p)
    return TaskIndex.from_onet(p)


@pytest.fixture
def df(index) -> pl.DataFrame:
    return parse_r6(FIX, "claude_ai", index)


def _v(df, metric, node_id="overall", geo_id="GLOBAL", taxonomy=None, start=MAY):
    f = (pl.col("metric") == metric) & (pl.col("node_id") == node_id) & (pl.col("geo_id") == geo_id)
    f &= pl.col("period_start") == start
    if taxonomy is not None:
        f &= pl.col("taxonomy") == taxonomy
    r = df.filter(f)
    assert r.height == 1, (metric, node_id, geo_id, r.height)
    return r["value"][0]


def test_r6_schema_and_periods(df):
    assert df.columns == schema.PANEL_COLUMNS
    assert set(df["release"]) == {"r6"}
    assert set(df["source"]) == {"claude_ai"}
    assert sorted(df["period_start"].unique().to_list()) == [date(2026, 4, 1), MAY]
    assert all(schema.is_canonical(m) for m in df["metric"].unique())
    assert set(df["taxonomy"]) <= schema.TAXONOMIES


def test_r6_maps_buckets_and_patterns(df):
    # patterns are renormalised over the five classified patterns; none stays a share of all
    assert _v(df, "directive_pct") == pytest.approx(30 / 97 * 100)
    assert _v(df, "learning_pct") == pytest.approx(16 / 97 * 100)
    assert _v(df, "none_pct") == 3.0
    five = ["directive", "feedback_loop", "task_iteration", "validation", "learning"]
    assert sum(_v(df, f"{p}_pct") for p in five) == pytest.approx(100)
    # buckets are kept as published
    assert _v(df, "automation_pct") == 49.48
    assert _v(df, "augmentation_pct") == 50.52
    assert _v(df, "automation_pct", "101") == 31.58
    assert _v(df, "usage_pct") == 100.0


def test_r6_artifact_and_means_kept(df):
    assert _v(df, "artifact_blog_or_article_pct", "101") == 12.5
    assert _v(df, "ai_autonomy_mean", "101") == 3.2
    assert _v(df, "human_only_time_mean", "101") == 2.5


def test_r6_taxonomy_levels_and_ids(df):
    t = df.filter(pl.col("metric") == "pct")
    got = {(r["taxonomy"], r["node_id"]) for r in t.iter_rows(named=True)
           if r["geo_id"] == "GLOBAL" and r["period_start"] == MAY}
    assert ("onet_dwa", "4.A.3.b.6.I01.D01") in got
    assert ("onet_iwa", "4.A.3.b.6.I01") in got
    assert ("onet_gwa", "4.A.2") in got
    assert ("soc_detailed", "15-1252.00") in got
    assert ("soc_major", "15") in got
    assert ("request", "fbfbf330-56ec-5632-b8da-c77bbfc1c87d") in got
    assert set(t.filter(pl.col("taxonomy") == "request")["level"]) == {0, 1}
    assert set(t.filter(pl.col("taxonomy") == "onet_gwa")["level"]) == {0}


def test_r6_task_match_by_id_then_text(df):
    assert _v(df, "pct", "101", taxonomy="onet_task") == 40.0
    # id 99999 is not an O*NET Task ID in the index; the text matches task 202
    assert _v(df, "pct", "202", taxonomy="onet_task") == 30.0
    # neither id nor text matches
    assert _v(df, "pct", "unmatched:juggle flaming torches for an audience",
              taxonomy="onet_task") == 20.0


def test_r6_geography(df):
    assert _v(df, "pct", "101", geo_id="USA", taxonomy="onet_task") == 50.0
    assert _v(df, "usage_pct", geo_id="USA") == 20.0
    assert _v(df, "usage_per_capita_index", geo_id="USA") == 1.4
    sub = df.filter(pl.col("geo_id") == "US-CA")
    assert sub["geo_level"].unique().to_list() == ["subregion"]
    assert sub["value"].to_list() == [30.0]


def test_unpublished_cells_stay_missing(df):
    # the fixture omits the 13-1011.00 SOC row for May: no row, no imputed 0
    soc = df.filter((pl.col("node_id") == "13-1011.00") & (pl.col("taxonomy") == "soc_detailed"))
    assert soc["period_start"].to_list() == [date(2026, 4, 1)]
    assert df.filter(pl.col("period_start") == MAY)["node_id"].is_in(["13-1011.00"]).sum() == 0
    # a metric that is absent for a node has no row either (no zero for the missing patterns)
    no_dir = (pl.col("node_id") == "202") & (pl.col("metric") == "directive_pct")
    assert df.filter(no_dir).height == 0


def test_unknown_metric_raises(index, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(FIX.read_text().splitlines()[0] + "\n"
                 "2026-05-01,2026-06-01,GLOBAL,global,overall,0,mystery_pct,1.0,Overall,-\n")
    with pytest.raises(ValueError, match="mystery_pct"):
        parse_r6(p, "claude_ai", index)


def test_all_zero_patterns_have_no_share(df):
    # a node whose five patterns are all 0 has no classified conversations: null, not NaN or 0
    z = df.filter(pl.col("node_id") == "aaaaaaaa-0000-5000-8000-000000000001")
    assert z.height == 5
    assert z["value"].null_count() == 5
