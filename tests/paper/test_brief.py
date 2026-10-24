"""Task 31: the executive brief is two pages and the paper body ends between pages 30 and 45.

Both tests render a copy of `docs/paper` (Quarto + XeLaTeX), so they are marked slow; they read
the copy's `_output/brief.pdf` and `_output/paper.pdf`.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAPER = Path(__file__).resolve().parents[2] / "docs" / "paper"
REFERENCES = re.compile(r"^\s*References\s*$", re.M)


def _render(tmp_path: Path, target: str) -> Path:
    """Render `target` (a file in docs/paper, or "" for the project) to PDF in a copy."""
    work = tmp_path / "paper"
    shutil.copytree(PAPER, work, ignore=shutil.ignore_patterns("_output", ".quarto"))
    cmd = ["quarto", "render", str(work / target) if target else str(work), "--to", "pdf"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-3000:]
    return work / "_output"


def references_page(pdf: Path) -> int:
    """The 1-based page holding the "References" heading."""
    from pypdf import PdfReader

    for i, page in enumerate(PdfReader(pdf).pages, start=1):
        if REFERENCES.search(page.extract_text() or ""):
            return i
    raise AssertionError(f"no References heading in {pdf}")


@pytest.mark.slow
def test_brief_is_two_pages(tmp_path):
    from pypdf import PdfReader

    out = _render(tmp_path, "brief.qmd")
    assert len(PdfReader(out / "brief.pdf").pages) == 2


@pytest.mark.slow
def test_paper_body_length(tmp_path):
    out = _render(tmp_path, "paper.qmd")
    assert 30 <= references_page(out / "paper.pdf") <= 45
