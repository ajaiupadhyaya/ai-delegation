"""Task 17: the Quarto skeleton renders and its section titles are fixed."""

from __future__ import annotations

import json
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


def _meta_date() -> str:
    return json.loads((PAPER / "_variables.yml").read_text(encoding="utf-8"))["meta"]["date"]


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join(p.extract_text() for p in PdfReader(path).pages)


def _render(tmp_path: Path, target: str, to: str) -> Path:
    """Render a copy of the project."""
    work = tmp_path / to / "paper"
    shutil.copytree(PAPER, work, ignore=shutil.ignore_patterns("_output", ".quarto"))
    cmd = ["quarto", "render", str(work / target) if target else str(work), "--to", to]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stderr[-3000:]
    return work / "_output"


@pytest.mark.slow
def test_renders_pdf_and_html(tmp_path):
    date = _meta_date()
    out = _render(tmp_path, "", "pdf")
    assert (out / "paper.pdf").stat().st_size > 0
    assert sorted(p.name for p in out.glob("*.pdf")) == ["brief.pdf", "paper.pdf"]
    assert date in _pdf_text(out / "paper.pdf")
    assert "Invalid Date" not in _pdf_text(out / "paper.pdf")
    out = _render(tmp_path, "", "html")
    html = (out / "paper.html").read_text(encoding="utf-8")
    assert date in html and "Invalid Date" not in html
    assert sorted(p.name for p in out.glob("*.html")) == ["brief.html", "paper.html"]


def test_brief_renders(tmp_path):
    out = _render(tmp_path, "brief.qmd", "pdf")
    assert (out / "brief.pdf").stat().st_size > 0
    text = _pdf_text(out / "brief.pdf")
    assert _meta_date() in text and "Invalid Date" not in text


@pytest.mark.slow
def test_generated_includes_render(tmp_path):
    """Task 18: every generated table and figure include renders in PDF and HTML, its labels
    resolve as cross-references and the variables expand (a copy of the project with one extra
    document that includes them all)."""
    work = tmp_path / "paper"
    shutil.copytree(PAPER, work, ignore=shutil.ignore_patterns("_output", ".quarto"))
    quarto = work / "_quarto.yml"
    text = quarto.read_text(encoding="utf-8")
    assert "    - brief.qmd\n" in text
    quarto.write_text(text.replace("    - brief.qmd\n", "    - brief.qmd\n    - check.qmd\n", 1))
    incs = sorted((work / "_generated").glob("*/*.md"))
    assert incs
    body = ["---", 'title: "Includes check"', "---", "", "MDE {{< var power.mde.h5 >}}.", ""]
    body += [f"{{{{< include {p.relative_to(work).as_posix()} >}}}}\n" for p in incs]
    body += ["See @tbl-rob-r07 and @fig-rq2-could-vs-does."]
    (work / "check.qmd").write_text("\n".join(body) + "\n", encoding="utf-8")
    for to in ("html", "pdf"):
        r = subprocess.run(
            ["quarto", "render", str(work / "check.qmd"), "--to", to],
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert r.returncode == 0, r.stderr[-3000:]
        assert "Unknown var" not in r.stderr and "WARNING" not in r.stderr, r.stderr[-3000:]
    html = (work / "_output/check.html").read_text(encoding="utf-8")
    assert 'href="#tbl-rob-r07"' in html and 'href="#fig-rq2-could-vs-does"' in html
    pdf = _pdf_text(work / "_output/check.pdf")
    assert "See Table" in pdf and "?? " not in pdf and "7.43" in pdf


@pytest.mark.slow
def test_deviations_render_onet_literally(tmp_path):
    """Appendix B quotes PAP §11 verbatim: its rendered text (HTML and PDF) holds "O*NET" as
    often as the source §11 does, with no emphasis opened between two of them (Minor 1 of the
    Task 34 review)."""
    from html import unescape

    from aideleg import paplog
    from aideleg.config import ROOT

    pap = (ROOT / "docs/pap/pre-analysis-plan.md").read_text(encoding="utf-8")
    body = "\n".join(paplog.section_11_lines(pap)[1:]).replace("O\\*NET", "O*NET")
    want = body.count("O*NET")
    assert want >= 2
    work = tmp_path / "paper"
    shutil.copytree(PAPER, work, ignore=shutil.ignore_patterns("_output", ".quarto"))
    quarto = work / "_quarto.yml"
    quarto.write_text(
        quarto.read_text(encoding="utf-8").replace(
            "    - brief.qmd\n", "    - brief.qmd\n    - onet.qmd\n", 1
        )
    )
    doc = ["---", 'title: "O*NET check"', "---", "", "START-OF-SECTION-11", ""]
    doc += ["{{< include _generated/appendix/deviations.md >}}", ""]
    (work / "onet.qmd").write_text("\n".join(doc) + "\n", encoding="utf-8")
    for to in ("html", "pdf"):
        r = subprocess.run(
            ["quarto", "render", str(work / "onet.qmd"), "--to", to],
            capture_output=True,
            text=True,
            timeout=900,
        )
        assert r.returncode == 0, r.stderr[-3000:]
    html = (work / "_output/onet.html").read_text(encoding="utf-8")
    # the last occurrence of each heading: the table of contents names them first
    section = html.rpartition("PAP §11, verbatim")[2].rpartition("PAP §10: corrections")[0]
    assert "O<em>NET" not in section and "O\\*NET" not in section
    text = unescape(re.sub(r"<[^>]+>", "", section))
    assert text.count("O*NET") == want, (text.count("O*NET"), want)
    pdf = _pdf_text(work / "_output/onet.pdf")
    pdf_section = pdf.rpartition("PAP §11, verbatim")[2].rpartition("PAP §10: corrections")[0]
    assert pdf_section.replace("\n", "").count("O*NET") == want
