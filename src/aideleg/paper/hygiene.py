r"""Source hygiene for the paper (Plan 4 Task 19): no typed numeral, no banned wording, no counted
robustness rows, resolvable citations, results paragraphs tied to generated material, section
lengths.

Numbers in the paper come only from generated files: a `{{< var … >}}` shortcode or a generated
include. `strip_allowed` removes what may legitimately hold a digit and does not render as a
number, in this order (every removal keeps the line breaks it spans, so line numbers survive):

1. YAML front matter, except the values that render (`RENDERED_YAML_KEYS`: title, subtitle,
   date, abstract, description), which stay and are scanned;
2. fenced code blocks: a plain block is removed only when it holds no numeral (otherwise its
   body stays and is scanned); raw blocks (`{=latex}`, `{=html}`) and executable chunks
   (`{python}`, `{r}`, …) are flagged outright by `forbidden_code` (only `RAW_ALLOWED` is
   exempt), and their bodies stay;
3. HTML comments;
   (then inline code: removed only when it looks like an identifier or a path, `IDENT_CODE`,
   and none of its `_./*-`-separated parts is purely numeric; any other inline code stays,
   where its digits are caught; inline raw or executable code is flagged by `forbidden_code`)
4. `{{< … >}}` shortcodes;
5. attribute blocks `{#id .class key=value}` (cross-reference labels included); the values of
   attributes that render (`RENDERED_ATTRS`, e.g. `fig-cap`) stay and are scanned;
6. citations and cross-refs `@[A-Za-z_][\w:.-]*` (including `[@key]`), so `@0.5` stays;
7. link and image targets `](…)`, but not link text;
8. PAP section references `§\d+(\.\d+)*`;
9. identifier tokens `\b[A-Za-z]+(\*[A-Za-z]+)*\d+[A-Za-z]*\b` (H1, RQ2, FF49, r6, R13, D21,
   H5b, t21); `*` passes only between letters, as in O*NET. Known limit: a letter-prefixed
   number such as `pp5` or `t2025` looks like an identifier and is stripped.

A numeral is any character with a Unicode numeric value (`unicodedata.numeric`): ASCII digits,
½, ①, ⅓, Ⅳ, …. Allowed: superscript digits ⁰-⁹ as exponents and subscript digits ₀-₉ as
identifier subscripts (t₂₁, b₀), each only directly after a letter, `)`, `]`, `⁻`, `⁺` or
another super/subscript digit (R², x⁻¹, (a+b)²); a free-standing ² is flagged.

Wording and robustness patterns run on each blank-line-separated block with its whitespace
collapsed, so a phrase wrapped across lines is caught; a hit is reported at the line where it
starts. The one disclaimer is Plan 2's `WORDING` (through the adapter); it is the only place a
`WORDING_BANNED` phrase may appear, and the exemption is applied to the collapsed text.
AEI data are conversations matched to O*NET tasks.
"""

from __future__ import annotations

import csv
import re
import unicodedata
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

RENDERED_YAML_KEYS = ("title", "subtitle", "date", "abstract", "description")
RENDERED_ATTRS = (
    "fig-cap",
    "tbl-cap",
    "fig-alt",
    "fig-subcap",
    "tbl-subcap",
    "lst-cap",
    "title",
    "caption",
    "alt",
)
# Raw blocks allowed by exact (stripped) content: paper.qmd's appendix switch.
RAW_ALLOWED = {("latex", "\\appendix")}
EXPONENT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉"

_FRONT = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*(\n|\Z)", re.S)
_FENCE = re.compile(
    r"^[ \t]*(?P<f>`{3,}|~{3,})[ \t]*(?P<info>[^\n]*)\n(?P<body>.*?)^[ \t]*(?P=f)[ \t]*$",
    re.S | re.M,
)
_FENCE_FORBIDDEN = re.compile(r"^\{\s*(=\w+|[A-Za-z]\w*)")
_INLINE_FORBIDDEN = re.compile(r"`\{[A-Za-z]\w*\}[^`\n]*`|`[^`\n]+`\{=\w+\}")
_ATTR_ITEM = r"(?:[#.][\w:.-]+|=\w+|-|[\w-]+=(?:\"[^\"]*\"|'[^']*'|[^\s}]+))"
_ATTRS = re.compile(r"\{\s*" + _ATTR_ITEM + r"(?:\s+" + _ATTR_ITEM + r")*\s*\}")
_ATTR_KV = re.compile(r"([\w-]+)=(?:\"([^\"]*)\"|'([^']*)'|([^\s}]+))")
_COMMENT = re.compile(r"<!--.*?-->", re.S)
_INLINE = re.compile(r"`([^`\n]+)`")
IDENT_CODE = re.compile(r"^[A-Za-z0-9_./*-]*[A-Za-z][A-Za-z0-9_./*-]*$")
SHORTCODE = re.compile(r"\{\{<.*?>\}\}", re.S)
_CITE = re.compile(r"@[A-Za-z_][\w:.-]*")
_TARGET = re.compile(r"\]\([^)]*\)")
_PAP_REF = re.compile(r"§\d+(\.\d+)*")
_IDENT = re.compile(r"\b[A-Za-z]+(?:\*[A-Za-z]+)*\d+[A-Za-z]*\b")
_KEY = re.compile(r"(?<![\w.@])@([A-Za-z_][\w:.-]*)")


def _blank(m: re.Match) -> str:
    """The match replaced by its line breaks only."""
    return "\n" * m.group(0).count("\n")


def _inline(m: re.Match) -> str:
    code = m.group(1)
    parts = [p for p in re.split(r"[_./*-]+", code) if p]
    if IDENT_CODE.match(code) and not any(p.isdigit() for p in parts):
        return ""
    return m.group(0)


def _front_rendered(m: re.Match) -> str:
    """Front matter with only the lines of `RENDERED_YAML_KEYS` kept (others blanked)."""
    out, keep = [], False
    lines = m.group(0).split("\n")
    for i, ln in enumerate(lines):
        top = re.match(r"^([A-Za-z_][\w-]*)\s*:", ln)
        if top:
            keep = top.group(1) in RENDERED_YAML_KEYS
        elif ln and not ln[0].isspace():
            keep = False
        out.append(ln if keep and 0 < i < len(lines) - 1 else "")
    return "\n".join(out)


def _fence_kind(info: str) -> str:
    """`raw`, `exec` or `plain` for a fence's info string."""
    m = _FENCE_FORBIDDEN.match(info.strip())
    if not m:
        return "plain"
    return "raw" if m.group(1).startswith("=") else "exec"


def _fence(m: re.Match) -> str:
    """Plain blocks without a numeral are removed; any other block keeps its body (fences
    blanked), so its digits are scanned."""
    body = m.group("body")
    if _fence_kind(m.group("info")) == "plain" and not _has_numeral(body):
        return _blank(m)
    return "\n" + body + "\n" * (m.group(0).count("\n") - body.count("\n") - 1)


def forbidden_code(text: str) -> list[tuple[int, str]]:
    """(line, opener) of every raw block (`{=latex}`, `{=html}`) and executable chunk
    (`{python}`, `{r}`, …), fenced or inline, outside comments; `RAW_ALLOWED` is exempt."""
    text = _COMMENT.sub(_blank, text)
    out = []
    for m in _FENCE.finditer(text):
        kind = _fence_kind(m.group("info"))
        if kind == "plain":
            continue
        fmt = m.group("info").strip().strip("{}= ")
        if kind == "raw" and (fmt, m.group("body").strip()) in RAW_ALLOWED:
            continue
        out.append((text.count("\n", 0, m.start()) + 1, m.group("f") + m.group("info").strip()))
    unfenced = _FENCE.sub(_blank, text)
    for m in _INLINE_FORBIDDEN.finditer(unfenced):
        out.append((unfenced.count("\n", 0, m.start()) + 1, m.group(0)))
    return sorted(out)


def _attrs(m: re.Match) -> str:
    """An attribute block replaced by the values of its rendered attributes."""
    vals = [
        next(v for v in g[1:] if v is not None)
        for g in _ATTR_KV.findall(m.group(0))
        if g[0] in RENDERED_ATTRS
    ]
    return " ".join(vals)


def _structural(text: str) -> str:
    """Front matter, fenced code and HTML comments, all blanked (for the non-numeral rules)."""
    text = _FRONT.sub(_blank, text)
    text = _FENCE.sub(_blank, text)
    return _COMMENT.sub(_blank, text)


def strip_allowed(text: str) -> str:
    """`text` without the parts that may hold a digit (module docstring), line breaks kept."""
    text = _FRONT.sub(_front_rendered, text)
    text = _FENCE.sub(_fence, text)
    text = _COMMENT.sub(_blank, text)
    text = _INLINE.sub(_inline, text)
    text = SHORTCODE.sub(_blank, text)
    text = _ATTRS.sub(_attrs, text)
    text = _CITE.sub("", text)
    text = _TARGET.sub("]", text)
    text = _PAP_REF.sub("", text)
    return _IDENT.sub("", text)


def _numeral_chars(line: str) -> list[str]:
    """Characters of `line` with a numeric value, except allowed super/subscript digits."""
    out = []
    for i, ch in enumerate(line):
        if unicodedata.numeric(ch, None) is None:
            continue
        prev = line[i - 1] if i else ""
        if ch in EXPONENT_DIGITS and (
            prev != "" and (prev.isalpha() or prev in ")]⁻⁺" or prev in EXPONENT_DIGITS)
        ):
            continue
        out.append(ch)
    return out


def _has_numeral(text: str) -> bool:
    return any(_numeral_chars(ln) for ln in text.splitlines())


def numerals_in_text(text: str) -> list[tuple[int, str]]:
    """The (1-based line, text) pairs where a numeral survives `strip_allowed`, plus every
    `forbidden_code` line (numbers must come from includes and vars)."""
    hits = [
        (i, ln.strip())
        for i, ln in enumerate(strip_allowed(text).splitlines(), 1)
        if _numeral_chars(ln)
    ]
    hits += [(ln, f"raw or executable code: {op}") for ln, op in forbidden_code(text)]
    return sorted(hits)


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


def _collapsed_hits(
    text: str, patterns: tuple[str, ...], exempt: str | None = None
) -> list[tuple[int, str, str]]:
    """(line, pattern, line) for each match in a blank-line-separated block with its
    whitespace collapsed; the line is where the match starts. `exempt` is masked first."""
    lines = text.splitlines()
    hits: set[tuple[int, str, str]] = set()
    block: list[int] = []
    for i in range(len(lines) + 1):
        if i < len(lines) and lines[i].strip():
            block.append(i)
            continue
        if block:
            parts, starts, pos = [], [], 0
            for j in block:
                piece = re.sub(r"\s+", " ", lines[j].strip())
                starts.append(pos)
                parts.append(piece)
                pos += len(piece) + 1
            flat = " ".join(parts)
            if exempt:
                flat = flat.replace(exempt, " " * len(exempt))
            for pat in patterns:
                for m in re.finditer(pat, flat, flags=re.I):
                    k = max(n for n, st in enumerate(starts) if st <= m.start())
                    hits.add((block[k] + 1, pat, lines[block[k]].strip()))
            block = []
    return sorted(hits)


def wording_hits(text: str) -> list[tuple[int, str, str]]:
    """(line, pattern, line) for each `WORDING_BANNED` match outside the exact `WORDING`."""
    return _collapsed_hits(text, WORDING_BANNED, exempt=WORDING)


def robustness_hits(text: str) -> list[tuple[int, str, str]]:
    """(line, pattern, line) for each `ROBUSTNESS_BANNED` match (case-insensitive, per block)."""
    return _collapsed_hits(text, ROBUSTNESS_BANNED)


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


_INCLUDE_LINE = re.compile(r"^\{\{<\s*include\s[^>]*>\}\}$")
_IMAGE_LINE = re.compile(r"^!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?$")
_LIST_ITEM = re.compile(r"^([-*+]|\d+[.)])\s")


def _prose(block: str) -> str | None:
    """The prose of a block, or None when the block is skipped: a heading, a list, or nothing
    but includes, images and fenced-div markers. Heading, include, image and `:::` lines are
    dropped first; a typed pipe table or `:` caption stays as prose."""
    keep = [
        ln.strip()
        for ln in block.splitlines()
        if ln.strip()
        and not ln.strip().startswith((":::", "#"))
        and not _INCLUDE_LINE.match(ln.strip())
        and not _IMAGE_LINE.match(ln.strip())
    ]
    if not keep or _LIST_ITEM.match(keep[0]):
        return None
    return "\n".join(keep)


def paragraphs(text: str) -> list[str]:
    """The prose of each blank-line-separated block of `text` (front matter, code and comments
    removed) that `_prose` does not skip."""
    blocks = re.split(r"\n[ \t]*\n", _structural(text))
    return [p for p in (_prose(b) for b in blocks) if p is not None]


def _typed_table(par: str) -> bool:
    return any(ln.startswith(("|", ": ")) for ln in par.splitlines())


def uncited_paragraphs(text: str) -> list[str]:
    """The `paragraphs` holding none of `@tbl-`, `@fig-`, `@sec-` or `{{< var`, and every
    typed pipe table or `:` caption (tables come from generated includes)."""
    return [
        p for p in paragraphs(text) if _typed_table(p) or not any(r in p for r in GENERATED_REFS)
    ]


def word_count(text: str) -> int:
    """Words after `strip_allowed`, each shortcode counted as one word."""
    body = strip_allowed(SHORTCODE.sub(" shortcode ", text))
    return len(re.findall(r"\S*\w\S*", body))


def is_stub(text: str) -> bool:
    return STUB in text
