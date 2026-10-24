"""The replication README (Plan 4 Task 32): the AEA Data Editor template's headings in order,
generated blocks current, every table and figure listed, the one disclaimer, the pre-registration.

AEI data are conversations matched to O*NET tasks.
"""

import csv
import json
import re

import pytest

from aideleg.config import ROOT
from aideleg.paper import hygiene, includes
from aideleg.paper.variables import PAP_COMMIT
from aideleg.results.common import WORDING

README = ROOT / "README.md"

# The headings of the template README (social-science-data-editors.github.io/template_README),
# in its wording and order; "Computational Details" is the template's heading for hardware.
HEADINGS = [
    "## Overview",
    "## Data Availability and Provenance Statements",
    "### Statement about Rights",
    "### Summary of Availability",
    "### Details on each Data Source",
    "## Dataset list",
    "## Computational requirements",
    "### Software Requirements",
    "### Controlled Randomness",
    "### Memory, Runtime, Storage Requirements",
    "#### Computational Details",
    "## Description of programs/code",
    "## Instructions to Replicators",
    "## List of tables and programs",
    "## References",
]


def _text() -> str:
    return README.read_text(encoding="utf-8")


def _docs_on_disk() -> bool:
    index = ROOT / "data/raw/sec/docs/INDEX.jsonl"
    if not index.is_file():
        return False
    for line in index.read_text(encoding="utf-8").splitlines():
        if line.strip() and not (ROOT / "data/raw" / json.loads(line)["dest"]).is_file():
            return False
    return True


def test_readme_headings_in_order():
    lines = _text().split("\n")
    positions = []
    for h in HEADINGS:
        assert h in lines, h
        positions.append(lines.index(h))
    assert positions == sorted(positions)


def test_readme_generated_blocks_current():
    text = _text()
    blocks = includes.readme_blocks()
    assert set(blocks) == set(includes.README_BLOCKS)
    for name, body in blocks.items():
        if name == "storage" and not _docs_on_disk():
            pytest.skip("the 10-K documents are not on disk: the storage block cannot be checked")
        begin, end = includes.readme_markers(name)
        assert text.count(begin) == 1 and text.count(end) == 1, name
        got = text.split(begin + "\n", 1)[1].split(end, 1)[0]
        assert got == body, name
    assert includes.render_readme(text) == text


def test_readme_lists_every_table_and_figure():
    text = _text()
    section = text.split("## List of tables and programs", 1)[1].split("## References", 1)[0]
    for name in ("tables.csv", "figures.csv"):
        with open(ROOT / "docs/paper" / name, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                assert f"`{row['id']}`" in section, (name, row["id"])


def test_readme_programs_resolve_for_every_exhibit(tmp_path):
    for row in csv.DictReader(open(ROOT / "docs/paper/tables.csv", encoding="utf-8")):
        assert includes.table_program(row["source"])
    for row in csv.DictReader(open(ROOT / "docs/paper/figures.csv", encoding="utf-8")):
        assert includes.figure_program(row["stem"])
    with pytest.raises(ValueError):
        includes.table_program("docs/elsewhere/x.md")
    with pytest.raises(ValueError):
        includes.figure_program("fig_unknown_x")


def test_readme_states_wording_once_and_no_banned_phrase():
    text = _text()
    assert text.count(WORDING) == 1
    assert hygiene.wording_hits(text) == []


def test_readme_states_preregistration():
    text = _text()
    assert "`pap-v1`" in text and PAP_COMMIT in text


def test_readme_no_fallback_and_clone_targets():
    text = _text()
    assert 'sha1(b"blob <len>\\0" + data)' in text
    for s in (
        "assert_confirmatory_recorded",
        "_record_commit",
        "docs/results/rq3/RECORD_COMMIT",
        "require_rq1_run_committed",
        "test_confirmatory_files_untouched",
    ):
        assert s in text, s


def test_readme_has_no_email_address():
    assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", _text())


def test_runtime_line_pending_without_check(tmp_path):
    assert includes.runtime_line(tmp_path / "check.md") == (
        "runtime: pending the fresh-clone check (Task 33)"
    )
    p = tmp_path / "check.md"
    p.write_text("# Check\n\n- Runtime of `make all`: 1 h 2 min\n", encoding="utf-8")
    assert "1 h 2 min" in includes.runtime_line(p)


def test_render_readme_replaces_only_blocks():
    begin, end = includes.readme_markers("seed")
    text = f"intro\n{begin}\nstale\n{end}\noutro\n"
    out = includes.render_readme(text, {"seed": "fresh\n"})
    assert out == f"intro\n{begin}\nfresh\n{end}\noutro\n"
    with pytest.raises(ValueError):
        includes.render_readme("no markers\n", {"seed": "x\n"})
