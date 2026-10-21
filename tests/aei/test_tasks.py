from pathlib import Path

import polars as pl
import pytest

from aideleg.acquire.sources import by_key
from aideleg.aei import schema
from aideleg.aei.tasks import TaskIndex, default_index, match_tasks, normalise_task_text
from aideleg.config import RAW


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


# --- O*NET-SOC 2019 vintage (Task 7b) ---------------------------------------------------


def _onet_2019(tmp_path: Path, rows: list[tuple[str, int, str]]) -> Path:
    """The O*NET 29.3 `Task Statements.txt` layout: tab-separated, no title column."""
    p = tmp_path / "tasks_2019.txt"
    lines = ["O*NET-SOC Code\tTask ID\tTask\tTask Type\tIncumbents Responding\tDate\t"
             "Domain Source"]
    lines += [f"{c}\t{i}\t{t}\tCore\t10\t08/2023\tIncumbent" for c, i, t in rows]
    p.write_text("\r\n".join(lines) + "\r\n")
    return p


def _crosswalk(tmp_path: Path, pairs: list[tuple[str, str]]) -> Path:
    p = tmp_path / "crosswalk.csv"
    pl.DataFrame({
        "O*NET-SOC 2010 Code": [a for a, _ in pairs], "O*NET-SOC 2010 Title": "t",
        "O*NET-SOC 2019 Code": [b for _, b in pairs], "O*NET-SOC 2019 Title": "t",
    }).write_csv(p)
    return p


def _build(tmp_path, new, old, walk) -> TaskIndex:
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    return TaskIndex.build(_onet_2019(tmp_path, new), _onet(legacy, old),
                           _crosswalk(tmp_path, walk))


def test_task_in_2019_file_uses_2019_codes(tmp_path):
    idx = _build(tmp_path, [("15-1252.00", 7, "Write code.")],
                 [("15-1132.00", 7, "Write code.")], [("15-1132.00", "15-1252.00")])
    assert idx.occupations_for(7) == ["15-1252.00"]
    assert idx.occupations_for_text("write code") == ["15-1252.00"]


def test_legacy_only_task_mapped_through_crosswalk(tmp_path):
    idx = _build(tmp_path, [("11-1011.00", 1, "Other.")],
                 [("15-1199.12", 42, "Manage documents.")], [("15-1199.12", "15-1299.03")])
    assert idx.occupations_for(42) == ["15-1299.03"]
    assert idx.occupations_for_text("Manage documents.") == ["15-1299.03"]


def test_split_crosswalk_returns_all_successors(tmp_path):
    idx = _build(tmp_path, [("11-1011.00", 1, "Other.")],
                 [("15-1199.00", 50, "Do computer work.")],
                 [("15-1199.00", "15-1299.00"), ("15-1199.00", "15-1255.00"),
                  ("15-1199.00", "13-1082.00")])
    assert idx.occupations_for(50) == ["13-1082.00", "15-1255.00", "15-1299.00"]


def test_text_matches_either_wording(tmp_path):
    idx = _build(tmp_path, [("15-1252.00", 7, "Write and test computer code.")],
                 [("15-1132.00", 7, "Write computer code.")], [("15-1132.00", "15-1252.00")])
    assert idx.task_ids_for("write computer code") == [7]
    assert idx.task_ids_for("Write and test computer code.") == [7]
    assert idx.occupations_for_text("write computer code") == ["15-1252.00"]


def test_provenance_counts(tmp_path):
    idx = _build(
        tmp_path,
        [("15-1252.00", 1, "A."), ("15-1252.00", 2, "B.")],
        [("15-1132.00", 1, "A."), ("15-1199.12", 3, "C."), ("99-9999.00", 4, "D.")],
        [("15-1132.00", "15-1252.00"), ("15-1199.12", "15-1299.03")],
    )
    assert idx.provenance() == {"onet_2019": 2, "crosswalk": 1, "unresolved": 1}
    assert idx.occupations_for(4) == []
    assert not idx.has_task_id(4)
    # every occupation is a 2019 code
    assert {o for t in (1, 2, 3) for o in idx.occupations_for(t)} == {"15-1252.00",
                                                                      "15-1299.03"}


# --- real data: r6 against the 2019 index ------------------------------------------------

_INDEX_KEYS = ("onet_29_3_tasks", "aei_onet_tasks", "onet_2010_2019_crosswalk")
_R6 = {"claude_ai": "aei_r6_claude_ai", "1p_api": "aei_r6_api"}
_needs_raw = pytest.mark.skipif(
    not all((RAW / by_key(k).dest).exists() for k in (*_INDEX_KEYS, *_R6.values())),
    reason="run `make data` first")


@pytest.fixture(scope="module")
def r6_global():
    from aideleg.aei.parse_r6 import parse_r6

    idx = default_index()
    frames = [parse_r6(RAW / by_key(k).dest, src, idx) for src, k in _R6.items()]
    df = pl.concat(frames).filter((pl.col("geo_id") == "GLOBAL") & (pl.col("metric") == "pct"))
    return idx, df


@pytest.mark.data
@_needs_raw
def test_r6_published_soc_codes_all_in_index(r6_global):
    idx, df = r6_global
    occs = idx.all_occupations()
    soc = df.filter(pl.col("taxonomy") == "soc_detailed")
    missing = soc.filter(~pl.col("node_id").is_in(sorted(occs)))
    share = (missing.group_by("source").agg(pl.col("value").sum())
             .join(soc.group_by("source").agg(total=pl.col("value").sum()), on="source"))
    worst = max((r["value"] / r["total"] * 100 for r in share.iter_rows(named=True)),
                default=0.0)
    assert missing.is_empty() or worst < 1.0, (
        f"{missing['node_id'].n_unique()} r6 SOC codes not in the index, "
        f"{worst:.2f}% of SOC pct: {sorted(missing['node_id'].unique())}")


@pytest.mark.data
@_needs_raw
def test_r6_task_mass_unmatched_below_2pct(r6_global):
    _, df = r6_global
    sentinel = pl.col("node_id").is_in(["unmatched:none", "unmatched:not_classified"])
    tasks = df.filter(pl.col("taxonomy") == "onet_task")
    un = tasks.filter(pl.col("node_id").str.starts_with("unmatched:") & ~sentinel)
    for source in _R6:
        periods = tasks.filter(pl.col("source") == source)["period_start"].n_unique()
        mass = un.filter(pl.col("source") == source)["value"].sum() / periods
        assert mass < 2.0, f"{source}: {mass:.2f}% of r6 task pct per period unmatched"


@pytest.mark.data
@_needs_raw
def test_default_index_is_2019_vintage():
    idx = default_index()
    prov = idx.provenance()
    assert prov["onet_2019"] > 18_000 and prov["crosswalk"] > 0
    occs = idx.all_occupations()
    # retired 2010 codes are gone
    assert "15-1132.00" not in occs and not any(o.startswith("15-1199") for o in occs)
    assert all(len(o) == 10 and o[2] == "-" and o[7] == "." for o in occs)
