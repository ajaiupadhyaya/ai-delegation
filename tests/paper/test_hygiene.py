"""Source hygiene of the paper (Plan 4 Task 19).

Every rule scans the paper sources: `docs/paper/**/*.qmd` (sections, appendices, `paper.qmd`,
`brief.qmd`, `brief_body.qmd`) and the caption/notes/alt cells of `docs/paper/tables.csv` and
`docs/paper/figures.csv`. `docs/redteam/**` is not a paper source (it quotes referee evidence)
and is not scanned. Fixtures under `tests/fixtures/paper/` show each rule firing.
"""

from __future__ import annotations

import ast
import csv
import re

import pytest

from aideleg.config import ROOT
from aideleg.paper import hygiene
from aideleg.robustness.upstream import WORDING

PAPER = ROOT / "docs" / "paper"
FIX = ROOT / "tests" / "fixtures" / "paper"
_EXCLUDED_DIRS = {"_output", ".quarto", "_generated"}
QMD = sorted(
    p for p in PAPER.rglob("*.qmd") if not _EXCLUDED_DIRS & set(p.relative_to(PAPER).parts)
)
CSVS = [PAPER / "tables.csv", PAPER / "figures.csv"]
SOURCES = QMD + CSVS
RESULTS_SECTIONS = [
    PAPER / "sections" / f
    for f in ("05-behaviour.qmd", "06-bridge.qmd", "07-market-evidence.qmd", "08-robustness.qmd")
]
CONFIRMATORY = (
    "rq1.h1.decision",
    "rq1.h2.decision",
    "rq1.h3.decision",
    "rq1.h4.decision",
    "rq3.h5.decision",
    "rq3.h5b.decision",
)


def _rel(path):
    return path.relative_to(ROOT).as_posix()


def _text(path):
    return path.read_text(encoding="utf-8")


def test_sources_found():
    names = {_rel(p) for p in SOURCES}
    assert "docs/paper/brief_body.qmd" in names
    assert "docs/paper/sections/08-robustness.qmd" in names
    assert not any(n.startswith("docs/redteam/") for n in names)


# --- numerals -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "line"),
    [("caption.qmd", 3), ("inline_code.qmd", 1), ("link_text.qmd", 3), ("plain.qmd", 1)],
)
def test_numeral_fixtures_flagged(name, line):
    hits = hygiene.numerals(FIX / name)
    assert [ln for ln, _ in hits] == [line], hits


@pytest.mark.parametrize(
    ("name", "lines"),
    [
        ("yaml_title.qmd", [2]),
        ("raw_block.qmd", [3]),
        ("exec_chunk.qmd", [3, 7]),
        ("at_number.qmd", [1]),
        ("unicode_numerals.qmd", [1]),
        ("star_ident.qmd", [1]),
        ("attr_caption.qmd", [1]),
    ],
)
def test_review_bypass_fixtures_flagged(name, lines):
    """Review fixes: rendered YAML values, raw/executable code, `@0.5`, non-ASCII numerals,
    `*` outside O*NET-style tokens and a rendered attribute value are all flagged."""
    hits = hygiene.numerals(FIX / name)
    assert sorted({ln for ln, _ in hits}) == lines, hits


def test_raw_block_allowlist_and_exponents():
    assert hygiene.forbidden_code("```{=latex}\n\\appendix\n```\n") == []
    assert hygiene.forbidden_code("```{=latex}\n\\vspace{1em}\n```\n") == [(1, "```{=latex}")]
    assert hygiene.numerals_in_text("R² and x⁻¹ and t₂₁ and (a+b)²") == []
    assert hygiene.numerals_in_text("a ² b") == [(1, "a ² b")]


def test_attribute_blocks_stripped_generally():
    assert hygiene.strip_allowed("# A {.unnumbered}") == "# A "
    assert hygiene.strip_allowed('![x](p.png){width=50% fig-align="center"}') == "![x]"
    assert "{{< var" not in hygiene.strip_allowed("{{< var a.b >}} {#tbl-x}")
    assert hygiene.numerals_in_text("Text {5} here") == [(1, "Text {5} here")]


@pytest.mark.parametrize(
    "text",
    [
        "logged as D-3 in PAP §11",
        "the clarifications C-55, C-77 and C-80, and the addition A-47",
        "the GPT-4 β beside the human β",
        "annual 10-K filings",
    ],
)
def test_names_with_digits_pass(text):
    """PAP §10/§11 entry ids, `10-K` and `GPT-4` are names, not reported numbers."""
    assert hygiene.numerals_in_text(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "D-3 moves β to 0.34",
        "the GPT-4 β is 0.71",
        "C-80 sets a tolerance of 1e-9",
        "in 10-K filings of 2024",
        "GPT-4o and E-3 and D-3a",
    ],
)
def test_numbers_beside_names_still_flagged(text):
    hits = hygiene.numerals_in_text(text)
    assert [ln for ln, _ in hits] == [1], hits


def test_numeral_fixture_ok_passes():
    assert hygiene.numerals(FIX / "ok.qmd") == []


def test_strip_allowed_keeps_link_text_and_odd_inline_code():
    assert "[7.43 pp]" in hygiene.strip_allowed("[7.43 pp](x.md)")
    assert "`r6_2025`" in hygiene.strip_allowed("`r6_2025`")
    assert hygiene.strip_allowed("`docs/results/confirmatory_h5.md`") == ""
    assert hygiene.strip_allowed("a\n<!--\n1\n-->\nb") == "a\n\n\n\nb"


def test_csv_numerals_name_the_cell(tmp_path):
    p = tmp_path / "tables.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "source", "caption", "notes"])
        w.writerow(["a", "x_2.md", "Fine caption (PAP §3.3; D10)", "Source: `docs/x_h5.md`."])
        w.writerow(["b", "y.md", "Results for 49 industries", "fine"])
    assert hygiene.numerals(p) == [(3, "caption: Results for 49 industries")]


@pytest.mark.parametrize("path", SOURCES, ids=_rel)
def test_no_numerals_outside_includes(path):
    hits = hygiene.numerals(path)
    assert hits == [], "\n".join(f"{_rel(path)}:{ln}: {t}" for ln, t in hits)


# --- wording --------------------------------------------------------------------------------


def test_wording_fixture_flagged():
    hits = hygiene.wording_hits(_text(FIX / "wording_bad.qmd"))
    assert [ln for ln, _, _ in hits] == [1]


def test_wording_allowed_only_inside_wording():
    assert hygiene.wording_hits(f"Intro.\n\n{WORDING}\n") == []
    assert hygiene.wording_hits(WORDING.replace("labour", "labor"))
    assert hygiene.wording_hits("We find no effect.")
    assert hygiene.wording_hits("The release caused it.")
    assert hygiene.wording_hits("because") == []


def test_wording_wrapped_across_lines_flagged():
    hits = hygiene.wording_hits(_text(FIX / "wording_wrapped.qmd"))
    assert [(ln, pat) for ln, pat, _ in hits] == [(3, r"\blabor market\b")]
    wrapped = WORDING.replace("the labour market", "the labour\n  market")
    assert hygiene.wording_hits(f"Intro.\n\n{wrapped}\n") == []


@pytest.mark.parametrize("path", SOURCES, ids=_rel)
def test_wording_rules(path):
    hits = hygiene.wording_hits(_text(path))
    assert hits == [], "\n".join(f"{_rel(path)}:{ln}: {pat}: {t}" for ln, pat, t in hits)


# --- robustness counts ----------------------------------------------------------------------


def test_robustness_patterns_match_the_appendix_gate():
    """The same three patterns as `test_summary_has_no_counts` (read from its source)."""
    tree = ast.parse(_text(ROOT / "tests" / "robustness" / "test_coverage.py"))
    found = [
        ast.literal_eval(n.value)
        for n in tree.body
        if isinstance(n, ast.Assign)
        and any(getattr(t, "id", None) == "COUNT_PATTERNS" for t in n.targets)
    ]
    assert found == [hygiene.ROBUSTNESS_BANNED]


@pytest.mark.parametrize("name", ["counts_of.qmd", "counts_most.qmd", "counts_in.qmd"])
def test_robustness_fixtures_flagged(name):
    assert hygiene.robustness_hits(_text(FIX / name))


def test_robustness_wrapped_across_lines_flagged():
    hits = hygiene.robustness_hits(_text(FIX / "counts_wrapped.qmd"))
    assert sorted({(ln, pat) for ln, pat, _ in hits}) == [
        (1, hygiene.ROBUSTNESS_BANNED[0]),
        (4, hygiene.ROBUSTNESS_BANNED[2]),
    ]


def test_robustness_section_no_counts():
    assert hygiene.robustness_hits(_text(FIX / "ok_rows.qmd")) == []
    path = PAPER / "sections" / "08-robustness.qmd"
    hits = hygiene.robustness_hits(_text(path))
    assert hits == [], "\n".join(f"{_rel(path)}:{ln}: {pat}: {t}" for ln, pat, t in hits)


# --- citations ------------------------------------------------------------------------------


def test_cited_keys_skip_crossrefs_code_and_email():
    text = (
        "See [@fama2015five; @holm1979simple], @tbl-a, @fig-b and @sec-c.\n"
        "Mail ajaiupad@gmail.com; `@notakey`.\n<!-- @hidden -->\nAs @newey1987simple:"
        " and by @0.5 pp."
    )
    assert hygiene.cited_keys(text) == {"fama2015five", "holm1979simple", "newey1987simple"}


def test_citations_resolve():
    bib = hygiene.bib_entries(_text(PAPER / "references.bib"))
    assert bib
    unlocatable = sorted(k for k, fields in bib.items() if not {"doi", "url"} & fields)
    assert unlocatable == [], unlocatable
    missing = {_rel(p): sorted(hygiene.cited_keys(_text(p)) - set(bib)) for p in QMD}
    missing = {k: v for k, v in missing.items() if v}
    assert missing == {}, missing


# --- results paragraphs ---------------------------------------------------------------------


def test_paragraph_rule_on_text():
    text = (
        "# Heading {#sec-x}\n\nThe slope is {{< var rq3.h5.b >}}.\n\n- a list item\n\n"
        "{{< include _generated/tables/x.md >}}\n\nA bare claim.\n\n::: {.note}\n:::\n"
    )
    assert hygiene.uncited_paragraphs(text) == ["A bare claim."]


def test_paragraph_rule_review_cases():
    """An include followed by prose is checked; a fenced div holding only an include or a
    figure is skipped; a typed pipe table or `:` caption is flagged even with a var in it."""
    bare = hygiene.uncited_paragraphs(_text(FIX / "paragraphs.qmd"))
    assert bare == [
        "Then a bare claim follows.",
        "| a | b |\n|---|---|\n| {{< var x.y >}} | c |",
        ": A typed caption with {{< var x.y >}} {#tbl-t}",
    ]


@pytest.mark.parametrize("path", RESULTS_SECTIONS, ids=_rel)
def test_results_paragraphs_cite_generated(path):
    bare = hygiene.uncited_paragraphs(_text(path))
    assert bare == [], f"{_rel(path)}: paragraphs without @tbl-/@fig-/@sec-/var: {bare}"


# --- lengths and stubs ----------------------------------------------------------------------


def _targets():
    with (PAPER / "section_targets.csv").open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def test_word_count_counts_shortcodes_once():
    assert hygiene.word_count("H1 is {{< var rq1.h1.decision_text >}} here [@x](y.md).") == 3


@pytest.mark.parametrize("row", _targets(), ids=lambda r: r["file"])
def test_section_lengths(row):
    text = _text(PAPER / row["file"])
    if hygiene.is_stub(text):
        pytest.skip("stub")
    n = hygiene.word_count(text)
    assert int(row["min_words"]) <= n <= int(row["max_words"]), (row["file"], n)


@pytest.mark.final
def test_no_stubs_left(request):
    """The final gate (Task 34). Run with `pytest -m final`; any other run skips it, since the
    prose tasks fill the stubs one by one."""
    if not re.search(r"\bfinal\b", request.config.option.markexpr or ""):
        pytest.skip("final gate: run with `pytest -m final` (Task 34)")
    stubs = [_rel(p) for p in QMD if hygiene.is_stub(_text(p))]
    assert stubs == []


# --- confirmatory decisions -----------------------------------------------------------------


def _has_var(text, key):
    return re.search(r"\{\{<\s*var\s+" + re.escape(key) + r"\s*>\}\}", text) is not None


@pytest.mark.parametrize("name", ["sections/00-abstract.qmd", "brief_body.qmd"])
def test_abstract_and_brief_report_every_confirmatory_decision(name):
    """Equal prominence for nulls: the abstract and the brief each print every confirmatory
    decision. Each hypothesis may use the raw `<h>.decision` variable or its prose form
    `<h>.decision_text` (Task 18), which the prose is expected to use."""
    text = _text(PAPER / name)
    if hygiene.is_stub(text):
        pytest.skip("stub")
    missing = [k for k in CONFIRMATORY if not (_has_var(text, k) or _has_var(text, k + "_text"))]
    assert missing == [], (name, missing)
