"""The H6 AI-term dictionary and text matching (PAP §6.1, decision D12).

Pure text functions: no network, no data. Primary terms are case-insensitive whole
phrases; a space matches any run of whitespace or hyphens; only the PLURAL terms
also match with a final "s". Acronyms are case-sensitive, bounded by non-alphanumerics,
and count only in a filing that also contains a GATE term. Overlaps resolve to the
longest, then leftmost, span across primaries and acronyms together.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from collections.abc import Sequence

PRIMARY_TERMS: tuple[str, ...] = (
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "neural network",
    "generative AI",
    "generative artificial intelligence",
    "large language model",
    "natural language processing",
    "computer vision",
    "reinforcement learning",
    "foundation model",
    "ChatGPT",
)
PLURAL: frozenset[str] = frozenset({"neural network", "large language model", "foundation model"})
ACRONYMS: tuple[str, ...] = ("AI", "A.I.", "GenAI", "LLM", "LLMs")
GATE: tuple[str, ...] = ("artificial intelligence", "generative AI")


def fts_phrases(terms: Sequence[str] = PRIMARY_TERMS) -> list[str]:
    """The phrases sent to full-text search: each term plus the plural of PLURAL terms."""
    out: list[str] = []
    for t in terms:
        out.append(t)
        if t in PLURAL:
            out.append(t + "s")
    return out


_BLOCKS = re.compile(
    r"<ix:header\b.*?</ix:header\s*>|<script\b.*?</script\s*>|<style\b.*?</style\s*>",
    re.IGNORECASE | re.DOTALL,
)
_TAG = re.compile(r"<[^>]*>")


def clean_text(raw: str, html: bool = True) -> str:
    """Drop header/script/style blocks, blank remaining tags, unescape, NFKC-normalise."""
    text = raw
    if html:
        text = _BLOCKS.sub(" ", text)
        text = _TAG.sub(" ", text)
        text = _html.unescape(text)
    return unicodedata.normalize("NFKC", text)


def _primary_re(term: str, plural: bool) -> re.Pattern[str]:
    body = r"[\s-]+".join(re.escape(w) for w in term.split(" "))
    if plural:
        body += "s?"
    return re.compile(r"(?<!\w)" + body + r"(?!\w)", re.IGNORECASE)


def _acronym_re(acr: str) -> re.Pattern[str]:
    return re.compile(r"(?<![A-Za-z0-9])" + re.escape(acr) + r"(?![A-Za-z0-9])")


def count_terms(text: str, terms: Sequence[str] = PRIMARY_TERMS) -> dict:
    """Count dictionary hits: {"primary", "acronym", "gated", "n_words"}."""
    spans: list[tuple[int, int, str, str]] = []  # (start, end, kind, name)
    for t in terms:
        for m in _primary_re(t, t in PLURAL).finditer(text):
            spans.append((m.start(), m.end(), "primary", t))
    for a in ACRONYMS:
        for m in _acronym_re(a).finditer(text):
            spans.append((m.start(), m.end(), "acronym", a))

    spans.sort(key=lambda s: (-(s[1] - s[0]), s[0]))
    taken: list[tuple[int, int]] = []
    primary = {t: 0 for t in terms}
    acronym = {a: 0 for a in ACRONYMS}
    for start, end, kind, name in spans:
        if any(start < e and s < end for s, e in taken):
            continue
        taken.append((start, end))
        (primary if kind == "primary" else acronym)[name] += 1

    # The gate looks for any occurrence of a GATE term, whatever the span resolution
    # and whatever `terms` is, so a narrower dictionary does not change which filings gate.
    gated = any(_primary_re(g, g in PLURAL).search(text) for g in GATE)
    if not gated:
        acronym = {a: 0 for a in ACRONYMS}
    return {
        "primary": primary,
        "acronym": acronym,
        "gated": gated,
        "n_words": len(re.findall(r"\S+", text)),
    }
