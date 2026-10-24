"""Task 17: the Quarto skeleton renders and its section titles are fixed."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[2] / "docs" / "paper"

TITLES = {
    "01-introduction.qmd": "Introduction",
    "02-related-literature.qmd": "Related literature",
    "03-data-and-measurement.qmd": "Data and measurement",
    "04-preregistration-and-methods.qmd": "Pre-registration and methods",
    "05-behaviour.qmd": "Behaviour: who delegates, for what, and is it changing? (RQ1)",
    "06-bridge.qmd": 'Bridge: industry exposure, "could" versus "does" (RQ2)',
    "07-market-evidence.qmd": "What the market evidence can and cannot yet say (RQ3 and H6)",
    "08-robustness.qmd": "Robustness",
    "09-limitations.qmd": "Limitations",
    "10-conclusion.qmd": "Conclusion",
}


def _first_heading(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#\s+(.*?)\s*(\{#[^}]*\})?\s*$", line)
        if m:
            return m.group(1)
    raise AssertionError(f"no heading in {path}")


def test_section_titles_fixed():
    for name, title in TITLES.items():
        assert _first_heading(PAPER / "sections" / name) == title, name


def _render(tmp_path: Path, target: str, to: str) -> Path:
    """Render a copy of the project (a placeholder bib if references.bib is absent)."""
    work = tmp_path / to / "paper"
    shutil.copytree(PAPER, work, ignore=shutil.ignore_patterns("_output", ".quarto"))
    bib = work / "references.bib"
    if not bib.exists():
        bib.write_text("", encoding="utf-8")
    cmd = ["quarto", "render", str(work / target) if target else str(work), "--to", to]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-3000:]
    return work / "_output"


@pytest.mark.slow
def test_renders_pdf_and_html(tmp_path):
    out = _render(tmp_path, "", "pdf")
    assert (out / "paper.pdf").stat().st_size > 0
    out = _render(tmp_path, "", "html")
    assert (out / "paper.html").stat().st_size > 0


def test_brief_renders(tmp_path):
    out = _render(tmp_path, "brief.qmd", "pdf")
    assert (out / "brief.pdf").stat().st_size > 0
