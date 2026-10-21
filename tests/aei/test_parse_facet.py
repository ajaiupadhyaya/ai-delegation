import re
from pathlib import Path

import polars as pl
import pytest

from aideleg.aei import schema
from aideleg.aei.parse_facet import load_metric_map, parse_facet_release
from aideleg.aei.tasks import TaskIndex
from aideleg.config import ROOT

FIX = Path(__file__).parent.parent / "fixtures" / "aei"
INVENTORY = ROOT / "docs/audit/tables/facet_inventory.md"
T = "act as advisers to student organizations."
U = "juggle flaming torches for an audience."
PLATFORM = "Claude AI (Free, Pro, and Max)"
HEADER = ("geo_id,geography,date_start,date_end,platform_and_product,facet,level,variable,"
          "cluster_name,value")


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
def iso(tmp_path: Path) -> Path:
    p = tmp_path / "iso.csv"
    p.write_text("iso_alpha_2,iso_alpha_3,country_name\nUS,USA,United States\n"
                 "CA,CAN,Canada\nNA,NAM,Namibia\n")
    return p


@pytest.fixture
def df(index, iso) -> pl.DataFrame:
    return parse_facet_release(FIX / "facet_small.csv", "r5", "claude_ai", index, iso=iso)


def _v(df, metric, node_id="overall", geo_id="GLOBAL", taxonomy=None, level=None):
    f = (pl.col("metric") == metric) & (pl.col("node_id") == node_id) & (pl.col("geo_id") == geo_id)
    if taxonomy is not None:
        f &= pl.col("taxonomy") == taxonomy
    if level is not None:
        f &= pl.col("level") == level
    r = df.filter(f)
    assert r.height == 1, (metric, node_id, geo_id, r.height)
    return r["value"][0]


def _inventory_pairs() -> set[tuple[str, str, str]]:
    out = set()
    for line in INVENTORY.read_text().splitlines():
        if re.match(r"\| r\d ", line):
            c = [x.strip() for x in line.strip().strip("|").split("|")]
            out.add((c[0], c[2], c[4]))
    return out


def test_every_inventoried_variable_is_mapped_or_ignored():
    m = load_metric_map()
    assert set(m["action"].unique()) <= {"map", "ignore"}
    assert m.filter(pl.col("reason").is_null() | (pl.col("reason") == "")).height == 0
    keys = m.select("facet", "variable")
    assert keys.is_duplicated().sum() == 0
    covered = {
        (rel, f, v)
        for rs, f, v in m.select("release_set", "facet", "variable").iter_rows()
        for rel in rs.split(";")
    }
    pairs = _inventory_pairs()
    assert len(pairs) > 100
    missing = pairs - covered
    assert not missing, sorted(missing)[:10]
    templates = {"<pattern>_pct", "use_case_<category>_pct"}
    mapped = m.filter(pl.col("action") == "map")
    for metric, tax in mapped.select("metric", "taxonomy").iter_rows():
        assert schema.is_canonical(metric) or metric in templates, metric
        assert tax in schema.TAXONOMIES, tax


def test_collaboration_renormalises_excluding_none_and_unclassified(df):
    assert _v(df, "directive_pct") == pytest.approx(37.5)
    assert _v(df, "feedback_loop_pct") == pytest.approx(12.5)
    assert _v(df, "task_iteration_pct") == pytest.approx(50.0)
    assert _v(df, "automation_pct") == pytest.approx(50.0)
    assert _v(df, "augmentation_pct") == pytest.approx(50.0)
    # none and not_classified are shares of all conversations, outside the denominator
    assert _v(df, "none_pct") == pytest.approx(10.0)
    assert _v(df, "not_classified_pct") == pytest.approx(50.0)


def test_task_level_collaboration_from_intersection(df):
    # task T: directive 30, task iteration 15, validation 15 classified; none 20
    assert _v(df, "directive_pct", "101", taxonomy="onet_task") == pytest.approx(50.0)
    assert _v(df, "validation_pct", "101", taxonomy="onet_task") == pytest.approx(25.0)
    assert _v(df, "automation_pct", "101", taxonomy="onet_task") == pytest.approx(50.0)
    assert _v(df, "augmentation_pct", "101", taxonomy="onet_task") == pytest.approx(50.0)
    assert _v(df, "none_pct", "101", taxonomy="onet_task") == pytest.approx(25.0)


def test_unpublished_pattern_stays_missing(df):
    # feedback loop is absent for task T: no row, never 0
    t = df.filter((pl.col("node_id") == "101") & (pl.col("metric") == "feedback_loop_pct"))
    assert t.height == 0
    # task U has only not_classified: bucket shares are null, not 0, and no pattern rows
    u = df.filter(pl.col("node_id") == f"unmatched:{U[:-1]}")
    assert u.filter(pl.col("metric") == "directive_pct").height == 0
    assert u.filter(pl.col("metric") == "automation_pct")["value"].to_list() == [None]
    assert _v(df, "not_classified_pct", f"unmatched:{U[:-1]}") == pytest.approx(100.0)


def test_geography_levels_normalised(df, index, iso, tmp_path):
    geo = df.select("geo_level", "geo_id").unique()
    assert set(geo.filter(pl.col("geo_level") == "country")["geo_id"]) == {
        "USA", "CAN", "NAM", "unmatched:not_classified"}
    assert _v(df, "count", geo_id="USA") == 500
    assert _v(df, "usage_pct", geo_id="NAM") == 3.0  # "NA" is Namibia, not a null
    assert geo.filter(pl.col("geo_id") == "US-CA")["geo_level"].to_list() == ["subregion"]
    assert _v(df, "directive_pct", geo_id="USA") == pytest.approx(75.0)
    assert set(geo.filter(pl.col("geo_id") == "GLOBAL")["geo_level"]) == {"global"}

    # r3 layout: US states are bare 2-letter codes under geography "state_us"
    p = tmp_path / "r3.csv"
    lead = 'CA,{0},2025-08-04,2025-08-11,"Claude AI (Free and Pro)",{0},0,usage_count,,{1}\n'
    p.write_text(HEADER + "\n" + lead.format("state_us", 7) + lead.format("country", 9))
    r3 = parse_facet_release(p, "r3", "claude_ai", index, iso=iso)
    assert _v(r3, "count", geo_id="US-CA") == 7
    assert _v(r3, "count", geo_id="CAN") == 9
    assert r3.filter(pl.col("geo_id") == "US-CA")["geo_level"].to_list() == ["subregion"]


def test_onet_task_cluster_names_matched_to_ids(df):
    tasks = df.filter((pl.col("taxonomy") == "onet_task") & (pl.col("metric") == "pct"))
    ids = dict(zip(tasks["node_name"], tasks["node_id"], strict=True))
    assert ids[T] == "101"
    assert ids[U] == f"unmatched:{U[:-1]}"
    assert _v(df, "count", "101", taxonomy="onet_task") == 80


def test_request_level_and_collaboration(df):
    assert _v(df, "pct", "Software development", taxonomy="request", level=1) == 90.0
    assert _v(df, "count", "Write code, tests, and docs", taxonomy="request", level=0) == 70
    sd = "Software development"
    assert _v(df, "automation_pct", sd, taxonomy="request", level=1) == pytest.approx(75.0)
    assert _v(df, "learning_pct", sd, taxonomy="request", level=1) == pytest.approx(25.0)


def test_numeric_means_and_categorical_shares(df):
    assert _v(df, "ai_autonomy_mean") == 3.25
    assert _v(df, "ai_autonomy_mean", "101", taxonomy="onet_task") == 2.5
    assert _v(df, "multitasking_pct") == pytest.approx(25.0)  # 30 / (30 + 90)
    assert _v(df, "use_case_work_pct") == pytest.approx(60.0)
    assert _v(df, "use_case_coursework_pct") == pytest.approx(10.0)
    assert df.filter(pl.col("metric").str.contains("median|histogram|success")).height == 0


def test_schema_source_definition_period(df, index, iso):
    assert df.columns == schema.PANEL_COLUMNS
    assert set(df["source"]) == {"claude_ai"}
    assert set(df["release"]) == {"r5"}
    assert set(df["definition"]) == {f"collab_v2|{PLATFORM}"}
    assert str(df["period_start"][0]) == "2026-02-05"
    assert str(df["period_end"][0]) == "2026-02-12"
    assert all(schema.is_canonical(m) for m in df["metric"].unique())
    assert set(df["taxonomy"]) <= schema.TAXONOMIES
    key = ["geo_level", "geo_id", "taxonomy", "level", "node_id", "metric"]
    assert df.select(key).is_duplicated().sum() == 0
    api = parse_facet_release(FIX / "facet_small.csv", "r5", "1p_api", index, iso=iso)
    assert set(api["source"]) == {"1p_api"}


def test_unmapped_variable_raises(index, iso, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(HEADER + "\n"
                 'GLOBAL,global,2026-02-05,2026-02-12,"1P API",mystery,0,mystery_count,x,1\n')
    with pytest.raises(ValueError, match="mystery"):
        parse_facet_release(p, "r5", "1p_api", index, iso=iso)
