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


@pytest.mark.skipif(not PANEL_PATH.exists(), reason="run `make panel` first")
def test_panel_row_counts_pinned():
    df = pl.read_parquet(PANEL_PATH)
    got: dict[str, dict[str, int]] = {}
    for release, source, n in df.group_by("release", "source").len().iter_rows():
        got.setdefault(release, {})[source] = n
    assert got == json.loads(COUNTS.read_text())
