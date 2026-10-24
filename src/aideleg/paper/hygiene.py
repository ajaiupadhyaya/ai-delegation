"""Source hygiene for the paper (Plan 4 Task 19): no typed numeral, no banned wording, no counted
robustness rows, resolvable citations, results paragraphs tied to generated material, section
lengths.

Numbers in the paper come only from generated files: a `{{< var … >}}` shortcode or a generated
include. `strip_allowed` removes everything that may legitimately hold a digit, in this order:

1. YAML front matter;
2. fenced code blocks;
3. HTML comments;
4. `{{< … >}}` shortcodes;
5. cross-reference labels `{#…}`;
6. citations and cross-refs `@[\\w:.-]+` (including `[@key]`);
7. link and image targets `](…)`, but not link text;
8. PAP section references `§\\d+(\\.\\d+)*`;
9. identifier tokens such as H1, RQ2, FF49, r6, R13, D21, H5b, t21.

Inline code is removed only when it looks like an identifier or a path (`IDENT_CODE`) and none of
its `_./*-`-separated parts is purely numeric; any other inline code stays in the text, where its
digits are caught. Inline code is handled after the HTML comments, before the shortcodes.
Every removal keeps the line breaks it spans, so line numbers survive.

The one disclaimer is Plan 2's `WORDING` (through the adapter); it is the only place a
`WORDING_BANNED` phrase may appear. AEI data are conversations matched to O*NET tasks.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from aideleg.robustness.upstream import WORDING

STUB = "<!-- STUB -->"
CSV_COLUMNS = ("caption", "notes", "alt")
GENERATED_REFS = ("@tbl-", "@fig-", "@sec-", "{{< var")
CROSSREF_PREFIXES = ("fig-", "tbl-", "sec-")

WORDING_BANNED = (
    r"\bjob market\b",
    r"\blabor market\b",
    r"\bdisplac\w*",
    r"\bjob (loss|losses|risk)\b",
    r"\breassur\w*",
    r"\bno effect\b",
    r"\bcaus(e|es|ed|al)\b",
    r"\b(workers|accountants|lawyers|people in \w+ jobs) (use|delegate)\b",
)
# The three `test_summary_has_no_counts` patterns (tests/robustness/test_coverage.py), PAP §8.1.
ROBUSTNESS_BANNED = (
    r"\b\d+\s+(of|out of)\b",
    r"\b(most|majority|all but|none of the)\b.*\bvariants?\b",
    r"\bsignificant in\b",
)

_FRONT = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(\n|\Z)", re.S)
_FENCE = re.compile(r"^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?^[ \t]*\1[ \t]*$", re.S | re.M)
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_INLINE = re.compile(r"`([^`\n]+)`")
IDENT_CODE = re.compile(r"^[A-Za-z0-9_./*-]*[A-Za-z][A-Za-z0-9_./*-]*$")
SHORTCODE = re.compile(r"\{\{<.*?>\}\}", re.S)
_LABEL = re.compile(r"\{#[^}]*\}")
_CITE = re.compile(r"@[\w:.-]+")
_TARGET = re.compile(r"\]\([^)]*\)")
_PAP_REF = re.compile(r"§\d+(\.\d+)*")
_IDENT = re.compile(r"\b[A-Za-z][A-Za-z*]*\d+[A-Za-z]*\b")
_DIGIT = re.compile(r"\d")
_KEY = re.compile(r"(?<![\w.@])@([\w:.-]+)")


def _blank(m: re.Match) -> str:
    """The match replaced by its line breaks only."""
    return "\n" * m.group(0).count("\n")


def _inline(m: re.Match) -> str:
    code = m.group(1)
    parts = [p for p in re.split(r"[_./*-]+", code) if p]
    if IDENT_CODE.match(code) and not any(p.isdigit() for p in parts):
        return ""
    return m.group(0)


def _structural(text: str) -> str:
    """Steps 1-3: front matter, fenced code, HTML comments."""
    text = _FRONT.sub(_blank, text)
    text = _FENCE.sub(_blank, text)
    return _COMMENT.sub(_blank, text)


def strip_allowed(text: str) -> str:
    """`text` without the parts that may hold a digit (module docstring), line breaks kept."""
    text = _structural(text)
    text = _INLINE.sub(_inline, text)
    text = SHORTCODE.sub(_blank, text)
    text = _LABEL.sub("", text)
    text = _CITE.sub("", text)
    text = _TARGET.sub("]", text)
    text = _PAP_REF.sub("", text)
    return _IDENT.sub("", text)


def numerals_in_text(text: str) -> list[tuple[int, str]]:
    """The (1-based line, stripped line) pairs where a digit survives `strip_allowed`."""
    return [
        (i, ln.strip())
        for i, ln in enumerate(strip_allowed(text).splitlines(), 1)
        if _DIGIT.search(ln)
    ]


def _csv_cells(path: Path) -> list[tuple[int, str, str]]:
    """(line, column, cell) for the scanned columns (`CSV_COLUMNS`) of a CSV file."""
    out = []
    with Path(path).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            for col in CSV_COLUMNS:
                if row.get(col):
                    out.append((reader.line_num, col, row[col]))
    return out


def numerals(path: Path) -> list[tuple[int, str]]:
    """The lines of `path` where a digit survives `strip_allowed`. For a `.csv`, the caption,
    notes and alt cells are scanned and the line is the record's (last) line in the file."""
    path = Path(path)
    if path.suffix == ".csv":
        return [
            (line, f"{col}: {hit}")
            for line, col, cell in _csv_cells(path)
            for _, hit in numerals_in_text(cell)
        ]
    return numerals_in_text(path.read_text(encoding="utf-8"))


def _line_hits(text: str, patterns: tuple[str, ...]) -> list[tuple[int, str, str]]:
    return [
        (i, pat, ln.strip())
        for i, ln in enumerate(text.splitlines(), 1)
        for pat in patterns
        if re.search(pat, ln, flags=re.I)
    ]


def wording_hits(text: str) -> list[tuple[int, str, str]]:
    """(line, pattern, line) for each `WORDING_BANNED` match outside the exact `WORDING`."""
    return _line_hits(text.replace(WORDING, ""), WORDING_BANNED)


def robustness_hits(text: str) -> list[tuple[int, str, str]]:
    """(line, pattern, line) for each `ROBUSTNESS_BANNED` match (case-insensitive, per line)."""
    return _line_hits(text, ROBUSTNESS_BANNED)


def cited_keys(text: str) -> set[str]:
    """The `@key`s of `text` (code, comments and front matter excluded) that are not `fig-`,
    `tbl-` or `sec-` cross-references. A trailing `.`, `:` or `-` is punctuation."""
    body = _INLINE.sub("", _structural(text))
    keys = {k.rstrip(".:-") for k in _KEY.findall(body)}
    return {k for k in keys if k and not k.startswith(CROSSREF_PREFIXES)}


def bib_entries(text: str) -> dict[str, set[str]]:
    """BibTeX key -> the lower-case field names of its entry (`@comment`/`@string` skipped)."""
    out: dict[str, set[str]] = {}
    starts = list(re.finditer(r"^@(\w+)\s*\{\s*([^,\s]+)\s*,", text, flags=re.M))
    for i, m in enumerate(starts):
        if m.group(1).lower() in ("comment", "string", "preamble"):
            continue
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        body = text[m.end() : end]
        out[m.group(2)] = {f.lower() for f in re.findall(r"^\s*(\w+)\s*=", body, flags=re.M)}
    return out


def _is_skipped_block(block: str) -> bool:
    first = block.lstrip()
    if first.startswith("#") or first.startswith("{{< include"):
        return True
    if re.match(r"([-*+]|\d+[.)])\s", first):
        return True
    return all(ln.strip().startswith(":::") for ln in block.splitlines() if ln.strip())


def paragraphs(text: str) -> list[str]:
    """Blank-line-separated blocks of `text` (front matter, code and comments removed) that are
    not a heading, a list item, an include or a fenced-div marker."""
    blocks = re.split(r"\n[ \t]*\n", _structural(text))
    return [b.strip() for b in blocks if b.strip() and not _is_skipped_block(b)]


def uncited_paragraphs(text: str) -> list[str]:
    """The `paragraphs` holding none of `@tbl-`, `@fig-`, `@sec-` or `{{< var`."""
    return [p for p in paragraphs(text) if not any(r in p for r in GENERATED_REFS)]


def word_count(text: str) -> int:
    """Words after `strip_allowed`, each shortcode counted as one word."""
    body = strip_allowed(SHORTCODE.sub(" shortcode ", text))
    return len(re.findall(r"\S*\w\S*", body))


def is_stub(text: str) -> bool:
    return STUB in text
