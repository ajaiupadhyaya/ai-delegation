"""D12 dictionary and matching rules (PAP §6.1)."""

import pytest

from aideleg.h6.dictionary import (
    ACRONYMS,
    GATE,
    PLURAL,
    PRIMARY_TERMS,
    clean_text,
    count_terms,
    fts_phrases,
)


def total(c: dict) -> int:
    return sum(c["primary"].values()) + sum(c["acronym"].values())


def test_twelve_terms_fifteen_phrases():
    assert PRIMARY_TERMS == (
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
    assert PLURAL == {"neural network", "large language model", "foundation model"}
    assert ACRONYMS == ("AI", "A.I.", "GenAI", "LLM", "LLMs")
    assert GATE == ("artificial intelligence", "generative AI")
    phrases = fts_phrases()
    assert len(phrases) == 15
    assert "neural networks" in phrases


def test_whitespace_and_hyphen_match():
    assert count_terms("Machine-learning")["primary"]["machine learning"] == 1
    assert count_terms("neural \n networks")["primary"]["neural network"] == 1


def test_longest_match_counts_once():
    c = count_terms("generative artificial intelligence")
    assert c["primary"]["generative artificial intelligence"] == 1
    assert c["primary"]["artificial intelligence"] == 0
    assert total(c) == 1


def test_acronyms_need_the_gate_and_longest_match_wins():
    c = count_terms("AI-driven tools in MAINE")
    assert c["gated"] is False
    assert c["acronym"]["AI"] == 0
    c = count_terms("AI-driven tools in MAINE artificial intelligence")
    assert c["gated"] is True
    assert c["acronym"]["AI"] == 1
    c = count_terms("Generative AI and AI")
    assert c["primary"]["generative AI"] == 1
    assert c["acronym"]["AI"] == 1
    c = count_terms("artificial intelligence LLMs")
    assert c["acronym"]["LLMs"] == 1
    assert c["acronym"]["LLM"] == 0


def test_dotted_acronym():
    c = count_terms("artificial intelligence and A.I. today, A.I., xA.I.")
    assert c["acronym"]["A.I."] == 2
    assert c["acronym"]["AI"] == 0


def test_acronyms_case_sensitive_and_bounded():
    c = count_terms("artificial intelligence ai Ai AI2 2AI GenAI LLM")
    assert c["acronym"]["AI"] == 0
    assert c["acronym"]["GenAI"] == 1
    assert c["acronym"]["LLM"] == 1


def test_chatgpt_case_insensitive_and_whole_word():
    c = count_terms("ChatGPT chatgpt CHATGPT ChatGPTs")
    assert c["primary"]["ChatGPT"] == 3


def test_plural_only_for_listed_terms():
    c = count_terms("machine learnings, large language models, foundation models")
    assert c["primary"]["machine learning"] == 0
    assert c["primary"]["large language model"] == 1
    assert c["primary"]["foundation model"] == 1


def test_whole_word_boundaries():
    c = count_terms("nonartificial intelligence, deep learnings")
    assert total(c) == 0


def test_terms_argument_restricts_dictionary():
    c = count_terms("machine learning and deep learning", terms=("deep learning",))
    assert c["primary"] == {"deep learning": 1}


def test_clean_text_strips_ix_header_and_entities():
    out = clean_text("<ix:header>secret</ix:header><p>A&amp;I</p>")
    assert out.strip() == "A&I"


def test_clean_text_script_style_nfkc_and_tag_gap():
    out = clean_text("<script>x()</script><style>p{}</style>machine<b>learning</b>ＡＩ")
    assert "x()" not in out and "p{}" not in out
    assert "machine learning" in out
    assert out.endswith("AI")


def test_clean_text_plain():
    assert clean_text("a < b", html=False) == "a < b"


@pytest.mark.parametrize("text,n", [("a  b\nc", 3), ("", 0)])
def test_word_count(text, n):
    assert count_terms(text)["n_words"] == n
