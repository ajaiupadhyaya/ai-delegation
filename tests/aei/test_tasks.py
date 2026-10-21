from pathlib import Path

import polars as pl

from aideleg.aei import schema
from aideleg.aei.tasks import TaskIndex, match_tasks, normalise_task_text


def _onet(tmp_path: Path, rows: list[tuple[str, int, str]]) -> Path:
    p = tmp_path / "onet.csv"
    df = pl.DataFrame(
        {
            "O*NET-SOC Code": [r[0] for r in rows],
            "Title": ["t"] * len(rows),
            "Task ID": [r[1] for r in rows],
            "Task": [r[2] for r in rows],
            "Task Type": ["Core"] * len(rows),
        }
    )
    df.write_csv(p)
    return p


def test_match_tolerates_case_space_punct():
    variants = [
        "Act as advisers to student organizations.",
        "act  as advisers to student organizations",
        "act as advisers to student organizations. ",
        "Act as advisers to student organizations.",
    ]
    assert len({normalise_task_text(v) for v in variants}) == 1
    assert normalise_task_text("Help ‘clients’ and “staff”.") == (
        "help 'clients' and \"staff\""
    )


def test_unmatched_is_null_not_dropped(tmp_path):
    idx = TaskIndex.from_onet(_onet(tmp_path, [("11-1011.00", 1, "Do a thing.")]))
    out = match_tasks(pl.Series("task_name", ["do a thing", "no such task"]), idx)
    assert out.columns == ["task_name", "task_id", "n_candidates"]
    assert out.schema["task_id"] == pl.Int64
    assert out.height == 2
    miss = out.filter(pl.col("task_name") == "no such task")
    assert miss["task_id"][0] is None and miss["n_candidates"][0] == 0


def test_shared_statement_lists_all_occupations(tmp_path):
    idx = TaskIndex.from_onet(
        _onet(tmp_path, [("11-1011.00", 5, "Shared."), ("11-1021.00", 5, "Shared."),
                         ("11-1021.00", 6, "Other.")])
    )
    assert idx.occupations_for(5) == ["11-1011.00", "11-1021.00"]
    assert idx.occupations_for(6) == ["11-1021.00"]
    assert idx.occupations_for(99) == []


def test_identical_text_different_ids(tmp_path):
    idx = TaskIndex.from_onet(
        _onet(tmp_path, [("11-1011.00", 9, "Same text."), ("11-1021.00", 3, "Same text.")])
    )
    assert idx.task_ids_for("same text") == [3, 9]
    out = match_tasks(pl.Series("task_name", ["same text"]), idx)
    assert out["n_candidates"][0] == 2 and out["task_id"][0] == 3


def test_is_canonical():
    assert "not_classified_pct" in schema.CANONICAL_METRICS
    assert schema.is_canonical("usage_pct")
    assert schema.is_canonical("artifact_code_snippet_pct")
    assert not schema.is_canonical("artifact_Code_pct")
    assert not schema.is_canonical("artifact_2d_pct")
    assert not schema.is_canonical("artifact_pct")
    assert not schema.is_canonical("bogus_pct")
    assert set(schema.PANEL_COLUMNS) >= {"release", "metric", "value"}
    assert len(schema.PANEL_COLUMNS) == 13


def test_occupations_for_text_unions_all_ids(tmp_path):
    idx = TaskIndex.from_onet(
        _onet(tmp_path, [("11-1011.00", 9, "Same text."), ("11-1021.00", 3, "Same text.")])
    )
    assert idx.occupations_for(3) == ["11-1021.00"]
    assert idx.occupations_for_text("  SAME text ") == ["11-1011.00", "11-1021.00"]
    assert idx.occupations_for_text("nope") == []


def test_null_name_kept(tmp_path):
    idx = TaskIndex.from_onet(_onet(tmp_path, [("11-1011.00", 1, "Do a thing.")]))
    out = match_tasks(pl.Series("task_name", [None, "do a thing"], dtype=pl.String), idx)
    assert out.height == 2
    assert out["task_id"][0] is None and out["n_candidates"][0] == 0
    assert out["task_id"][1] == 1
