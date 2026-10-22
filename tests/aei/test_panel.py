import json
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from aideleg.aei import panel
from aideleg.aei.schema import PANEL_COLUMNS
from aideleg.config import DERIVED

PANEL_PATH = DERIVED / "aei_panel.parquet"
COUNTS = Path(__file__).parent / "expected_counts.json"
PERIOD = (date(2026, 5, 1), date(2026, 6, 1))
_SCHEMA = {
    "release": pl.String, "period_start": pl.Date, "period_end": pl.Date,
    "source": pl.String, "geo_level": pl.String, "geo_id": pl.String,
    "taxonomy": pl.String, "level": pl.Int64, "node_id": pl.String,
    "node_name": pl.String, "metric": pl.String, "value": pl.Float64,
    "definition": pl.String,
}


def rows(*specs, release="r6", taxonomy="onet_task", geo="GLOBAL") -> pl.DataFrame:
    """specs: (node_id, metric, value)."""
    return pl.DataFrame(
        {
            "release": release, "period_start": PERIOD[0], "period_end": PERIOD[1],
            "source": "claude_ai", "geo_level": "global", "geo_id": geo,
            "taxonomy": taxonomy, "level": 0,
            "node_id": [s[0] for s in specs], "node_name": [s[0] for s in specs],
            "metric": [s[1] for s in specs], "value": [s[2] for s in specs],
            "definition": "collab_v2",
        },
        schema=_SCHEMA,
    ).select(PANEL_COLUMNS)


def _pats(node, d, f, t, v, lr, extra=()):
    return [(node, "directive_pct", d), (node, "feedback_loop_pct", f),
            (node, "task_iteration_pct", t), (node, "validation_pct", v),
            (node, "learning_pct", lr), *extra]


def test_check_panel_shares_sum():
    ok = panel.check_panel(rows(("1", "pct", 60.0), ("2", "pct", 39.8)))
    passed, detail = ok.checks["shares_sum"]
    assert passed
    assert "unpublished mass" in detail  # a 0.2-point shortfall is recorded, not failed
    short = panel.check_panel(rows(("1", "pct", 60.0), ("2", "pct", 30.0)))
    passed, detail = short.checks["shares_sum"]
    assert passed and "unpublished mass" in detail
    over = panel.check_panel(rows(("1", "pct", 60.0), ("2", "pct", 41.0)))
    assert not over.checks["shares_sum"][0]
    assert not over.ok


def test_check_panel_shares_sum_is_per_group():
    a = rows(("1", "pct", 70.0))
    b = rows(("1", "pct", 70.0), geo="USA")  # a second geography is a separate group
    assert panel.check_panel(pl.concat([a, b])).checks["shares_sum"][0]


def test_check_panel_pattern_partition():
    good = rows(*_pats("1", 20, 10, 40, 10, 20,
                       [("1", "automation_pct", 30.0), ("1", "augmentation_pct", 70.0)]))
    assert panel.check_panel(good).checks["pattern_partition"][0]
    bad = rows(*_pats("1", 20, 10, 40, 10, 20,
                      [("1", "automation_pct", 30.0), ("1", "augmentation_pct", 60.0)]))
    assert not panel.check_panel(bad).checks["pattern_partition"][0]
    # incomplete patterns are not tested
    part = rows(("1", "directive_pct", 20.0), ("1", "automation_pct", 30.0))
    assert panel.check_panel(part).checks["pattern_partition"][0]


def test_r6_automation_bucket_consistent_with_patterns():
    ok = rows(*_pats("1", 20, 10, 40, 10, 20, [("1", "automation_pct", 30.4)]))
    assert panel.check_panel(ok).checks["r6_bucket_consistency"][0]
    off = rows(*_pats("1", 20, 10, 40, 10, 20, [("1", "automation_pct", 35.0)]))
    passed, detail = panel.check_panel(off).checks["r6_bucket_consistency"]
    assert not passed and "1 " in detail
    # only r6 is tested; a published value is never altered
    other = rows(*_pats("1", 20, 10, 40, 10, 20, [("1", "automation_pct", 35.0)]), release="r5")
    assert panel.check_panel(other).checks["r6_bucket_consistency"][0]


def test_check_panel_schema_and_duplicates():
    dup = pl.concat([rows(("1", "pct", 10.0)), rows(("1", "pct", 10.0))])
    assert not panel.check_panel(dup).checks["unique_keys"][0]
    bad = rows(("1", "mystery", 1.0))
    assert not panel.check_panel(bad).checks["canonical_metrics"][0]


def test_report_markdown_lists_every_check():
    rep = panel.check_panel(rows(("1", "pct", 50.0)))
    md = rep.to_markdown()
    for name in rep.checks:
        assert name in md
    assert "unmatched" in md


@pytest.mark.data
@pytest.mark.skipif(not PANEL_PATH.exists(), reason="run `make panel` first")
def test_panel_row_counts_pinned():
    df = pl.read_parquet(PANEL_PATH)
    got: dict[str, dict[str, int]] = {}
    for release, source, n in df.group_by("release", "source").len().iter_rows():
        got.setdefault(release, {})[source] = n
    assert got == json.loads(COUNTS.read_text())


def test_unpublished_cells_stay_missing(monkeypatch, tmp_path):
    """Review Focus #2 at panel level: build_panel over r1-r6 (fixtures at their raw paths)
    keeps every unpublished cell missing -- no row, or a null value -- and never 0."""
    from aideleg.acquire.sources import by_key
    from aideleg.aei import parse_facet
    from aideleg.aei.tasks import TaskIndex

    fx = Path(__file__).parent.parent / "fixtures" / "aei"
    copies = {"aei_r1_task_pct": "r1_task_pct_small.csv",
              "aei_r2_task_pct": "r2_task_pct_small.csv"}
    for n in (3, 4, 5):
        for key in ("claude_ai", "api"):
            copies[f"aei_r{n}_{key}"] = "facet_small.csv"
    for key in ("claude_ai", "api"):
        copies[f"aei_r6_{key}"] = "r6_small.csv"
    mm = parse_facet.load_metric_map()
    for key, name in copies.items():
        dest = tmp_path / by_key(key).dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        text = (fx / name).read_text()
        if name == "facet_small.csv":  # keep the (facet, variable) pairs this release has
            rel = key.split("_")[1]
            have = set(mm.filter(pl.col("release_set").str.split(";").list.contains(
                pl.lit(rel))).select("facet", "variable").iter_rows())
            raw = pl.read_csv(fx / name, infer_schema=False)
            raw = raw.filter(pl.struct("facet", "variable").map_elements(
                lambda r, have=have: (r["facet"], r["variable"]) in have,
                return_dtype=pl.Boolean))
            text = raw.write_csv()
        dest.write_text(text)
    (tmp_path / "aei/r1/automation_vs_augmentation.csv").write_text(
        (fx / "r1_collab_small.csv").read_text())
    (tmp_path / "aei/r2/automation_vs_augmentation_by_task.csv").write_text(
        (fx / "r2_collab_small.csv").read_text())
    onet = tmp_path / "onet.csv"
    pl.DataFrame({"O*NET-SOC Code": ["25-1011.00", "13-1011.00"], "Title": ["t", "t"],
                  "Task ID": [101, 202],
                  "Task": ["Act as advisers to student organizations.", "Write reports"],
                  "Task Type": ["Core", "Core"]}).write_csv(onet)
    index = TaskIndex.from_onet(onet)
    iso = tmp_path / by_key("aei_geo_iso").dest
    iso.parent.mkdir(parents=True, exist_ok=True)
    iso.write_text("iso_alpha_2,iso_alpha_3,country_name\nUS,USA,United States\n"
                   "CA,CAN,Canada\nNA,NAM,Namibia\n")
    monkeypatch.setattr(panel, "default_index", lambda raw=None: index)
    monkeypatch.setattr(parse_facet, "RAW", tmp_path)
    df = panel.build_panel(raw=tmp_path, write=False)
    assert set(df["release"].unique()) == {"r1", "r2", "r3", "r4", "r5", "r6"}
    pats = [*panel.PATTERNS, "automation_pct", "augmentation_pct"]

    def cell(release, node, metric, **kw):
        f = (pl.col("release") == release) & (pl.col("node_id") == node) & \
            (pl.col("metric") == metric)
        for k, v in kw.items():
            f &= pl.col(k) == v
        return df.filter(f)

    # r1 publishes no task-level collaboration: no task rows for any pattern or bucket
    r1_task = df.filter((pl.col("release") == "r1") & (pl.col("taxonomy") == "onet_task"))
    assert r1_task.filter(pl.col("metric").is_in(pats)).height == 0
    # r2: a fully filtered task has null pattern and bucket shares, never 0
    for m in pats:
        assert cell("r2", "202", m)["value"].to_list() == [None]
    # r3-r5: an absent pattern has no row; a task with only not_classified gets null buckets
    u = "unmatched:juggle flaming torches for an audience"
    for r in ("r3", "r4", "r5"):
        assert cell(r, "101", "feedback_loop_pct").height == 0
        assert cell(r, u, "directive_pct").height == 0
        assert set(cell(r, u, "automation_pct")["value"].to_list()) == {None}
    # r6: an unpublished month/occupation cell and an absent metric have no row
    may = date(2026, 5, 1)
    assert cell("r6", "13-1011.00", "pct", period_start=may).height == 0
    assert cell("r6", "202", "directive_pct").height == 0
    # nothing unpublished became 0. The 0s that do appear are published 0s (r2's by-task
    # file, r6's all-zero node) or parse_facet's documented explicit 0 for an absent
    # none / not_classified intersection cell (classified total known, so 0 conversations)
    zeros = df.filter(pl.col("value") == 0.0)
    facet = zeros.filter(pl.col("release").is_in(["r3", "r4", "r5"]))
    assert set(facet["metric"].unique()) <= {"none_pct", "not_classified_pct"}
    r1_zero = zeros.filter(pl.col("release") == "r1")
    assert r1_zero.height == 0
