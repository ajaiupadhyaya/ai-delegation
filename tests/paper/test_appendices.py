"""Generated appendices (Plan 4 Task 21): pre-registration, deviations, disclosures, robustness,
data and replication."""

import json
import re
from pathlib import Path

import pytest

from aideleg import paplog
from aideleg.config import RAW, ROOT
from aideleg.paper import includes, variables

PAP = ROOT / "docs/pap/pre-analysis-plan.md"
POST = ROOT / "docs/disclosures/post-freeze.md"
ROB = ROOT / "docs/results/robustness"


def _body(text: str, heading: str) -> str:
    """The lines after `heading` up to the next heading of the same or a higher level."""
    lines = text.split("\n")
    i = lines.index(heading)
    level = len(heading) - len(heading.lstrip("#"))
    j = next(
        (k for k in range(i + 1, len(lines)) if re.match(rf"^#{{1,{level}}} ", lines[k])),
        len(lines),
    )
    return "\n".join(lines[i + 1 : j]).strip("\n")


def _table_rows(text: str) -> list[list[str]]:
    rows = []
    for line in text.splitlines():
        if line.startswith("|") and not re.fullmatch(r"\|(\s*:?-+:?\s*\|)+", line):
            rows.append([c.strip() for c in line.strip().strip("|").split(" | ")])
    return rows


FIXTURE_PAP = """# PAP

## 10. Corrections to the design spec

Spec corrections here.

### 10.1 Corrections of fact

- **S1.** something

## 11. Deviations

*None at freeze.*

### Additions (D20)

### A-1. Addition: `key_one` (2026-10-22)
- Type: addition under D20 (descriptive; not a deviation)
- URL: https://example.org/a

### A-2. Addition (set): `sec_fts/` (2026-10-23)
- Type: addition under D20 (pre-specified; not a deviation)
- Records: 3; retrieved (UTC) from 2026-10-23T01:00:00Z to 2026-10-23T02:00:00Z

### Clarifications (pre-result)

### C-1. Clarification: A rule (2026-10-22)
- Type: clarification (pre-result)
- Results seen: no
- Rule: a | b

### Deviations after the freeze

### D-1. Deviation: A change (2026-10-23)
- Type: deviation
- Results seen: yes
- Approved by Ajai: yes
"""

EMPTY_PAP = """# PAP

## 10. Corrections to the design spec

Spec corrections here.

## 11. Deviations

*None at freeze.*
"""


@pytest.fixture(scope="module")
def out(tmp_path_factory) -> Path:
    return tmp_path_factory.mktemp("appendix")


def test_preregistration_verbatim(out):
    text = includes.preregistration_appendix(PAP, out_dir=out).read_text(encoding="utf-8")
    pap = PAP.read_text(encoding="utf-8")
    table = includes.extract_table(_body(pap, "### 0.3 Decision register"), None)
    assert "\n".join(table) in text
    assert _body(pap, "### 0.1 Signature") in text
    block = pap.split("<!-- BEGIN GENERATED: code binding -->\n", 1)[1]
    block = block.split("<!-- END GENERATED: code binding -->", 1)[0].strip("\n")
    assert block in text
    pv = variables.pap_values()
    assert f"`{pv['tag']}`" in text and pv["commit"] in text


def test_deviations_verbatim(out):
    text = includes.deviations_appendix(PAP, out_dir=out).read_text(encoding="utf-8")
    pap = PAP.read_text(encoding="utf-8")
    body = "\n".join(paplog.section_11_lines(pap)[1:]).strip("\n")
    assert body in text
    assert _body(pap, "## 10. Corrections to the design spec") in text
    rows = _table_rows(text.split(body)[0])
    ids = [f"{e['kind']}-{e['n']}" for e in paplog.entries(PAP)]
    assert [r[0] for r in rows[1:]] == ids


def test_deviation_summary_rows(tmp_path):
    pap = tmp_path / "pap.md"
    pap.write_text(FIXTURE_PAP, encoding="utf-8")
    text = includes.deviations_appendix(pap, out_dir=tmp_path).read_text(encoding="utf-8")
    body = "\n".join(paplog.section_11_lines(FIXTURE_PAP)[1:]).strip("\n")
    rows = _table_rows(text.split(body)[0])
    assert rows[0] == ["id", "kind", "date", "results seen"]
    assert [r[:2] for r in rows[1:]] == [
        ["A-1", "addition"],
        ["A-2", "addition"],
        ["C-1", "clarification"],
        ["D-1", "deviation"],
    ]
    seen = {r[0]: r[3] for r in rows[1:]}
    assert seen == {"A-1": "not stated", "A-2": "not stated", "C-1": "no", "D-1": "yes"}
    assert rows[1][2] == "2026-10-22"
    assert "Additions (D20)" not in "".join(r[0] for r in rows)
    assert "Spec corrections here." in text and "### 10.1 Corrections of fact" in text
    assert "None at freeze, and none since." not in text


def test_deviations_none(tmp_path):
    pap = tmp_path / "pap.md"
    pap.write_text(EMPTY_PAP, encoding="utf-8")
    text = includes.deviations_appendix(pap, out_dir=tmp_path).read_text(encoding="utf-8")
    assert "None at freeze, and none since." in text
    assert "*None at freeze.*" in text
    assert _table_rows(text) == []


def test_disclosures_verbatim(out):
    text = includes.disclosures_appendix(PAP, POST, out_dir=out).read_text(encoding="utf-8")
    pap = PAP.read_text(encoding="utf-8")
    disclosures = _body(pap, "### 0.4 Disclosures")
    assert disclosures.startswith("What was seen before this plan was frozen:")
    assert disclosures in text
    post = POST.read_text(encoding="utf-8").strip("\n")
    assert post in text
    assert text.index(disclosures) < text.index(post)


def test_post_freeze_bullets_cite_sources():
    bullets = [ln for ln in POST.read_text(encoding="utf-8").splitlines() if ln.startswith("- ")]
    assert len(bullets) >= 14
    for b in bullets:
        assert re.search(r"Source: .*(ledger|§11 [ACD]-\d+)", b), b
    text = POST.read_text(encoding="utf-8")
    for needle in ("C-31", "C-55", "D-2", "D-3", "C-77", "C-80", "git stash", "708", "87"):
        assert needle in text, needle
    for banned in ("no effect", "job risk", "displac", " he ", " his ", " him "):
        assert banned not in text.lower(), banned


def test_robustness_appendix_row_order(out):
    text = includes.robustness_appendix(out_dir=out).read_text(encoding="utf-8")
    files = ["summary.md", "implementation_choices.md"] + sorted(
        p.name for p in ROB.glob("R[0-9][0-9].md")
    )
    assert len(files) > 30
    pos = []
    for name in files:
        src = (ROB / name).read_text(encoding="utf-8")
        for table in includes.tables_in(src):
            for line in table:
                if "](" not in line:
                    assert line in text, (name, line)
        title = src.splitlines()[0]
        assert title.startswith("# ")
        pos.append(text.index("#" + title.split(" {")[0]))
    assert pos == sorted(pos)
    assert "\\begin{landscape}" in text and "\\end{landscape}" in text
    assert "](R01.md)" not in text and "](#app-rob-r01)" in text
    assert not re.search(r"^# ", text, re.M)


def test_data_appendix_lists_every_key(out):
    text = includes.data_appendix(out_dir=out).read_text(encoding="utf-8")
    manifest = json.loads((RAW / "MANIFEST.json").read_text(encoding="utf-8"))
    rows = _table_rows(text)
    first = [r[0] for r in rows]
    for key in manifest:
        if key.startswith("sec_fts/"):
            assert first.count(f"`{key}`") == 0, key
            continue
        assert first.count(f"`{key}`") == 1, key  # sec_docs_index: its one set row
    assert not any(c.startswith("`sec_fts/") and c != "`sec_fts/`" for c in first)
    fts_keys = [k for k in manifest if k.startswith("sec_fts/")]
    digest = paplog.set_digest((k, manifest[k]["sha256"]) for k in fts_keys)
    (fts,) = [r for r in rows if r[0] == "`sec_fts/`"]
    assert f"{len(fts_keys)} records" in " ".join(fts) and digest[:16] in " ".join(fts)
    assert digest in text
    index = RAW / paplog.SET_INDEX_FILE
    if index.is_file():
        n = sum(1 for ln in index.read_text().splitlines() if ln.strip())
    else:
        latest = [e for e in paplog.entries(PAP) if e["title"].strip("`") == paplog.SET_INDEX_KEY][
            -1
        ]
        n = paplog.set_entry_fields(latest)["count"]
    (idx,) = [r for r in rows if r[0] == f"`{paplog.SET_INDEX_KEY}`"]
    assert f"{n} documents" in " ".join(idx)
    assert manifest[paplog.SET_INDEX_KEY]["sha256"][:16] in " ".join(idx)
    added = {r[0].strip("`") for r in rows if r[-1].startswith("added under D20")}
    assert "ne_admin0_50m" in added and "aei_r1_collab" not in added


def test_data_appendix_environment_dag_seed(out):
    text = includes.data_appendix(out_dir=out).read_text(encoding="utf-8")
    for pkg in ("numpy", "polars", "scipy", "statsmodels", "pandas", "pypdf", "pytest"):
        assert re.search(rf"^\| `{pkg}` \| [0-9][^ |]* \|", text, re.M), pkg
    assert "Python 3.12" in text
    for target in ("panel", "exposure", "robustness", "paper", "data/derived/aei_panel.parquet"):
        assert re.search(rf"^\| `{re.escape(target)}` \|", text, re.M), target
    assert "20261021" in text
    assert "README.md" in text


def test_main_writes_appendices():
    from aideleg.paper import __main__ as m

    assert "appendix" in Path(m.__file__).read_text(encoding="utf-8")
