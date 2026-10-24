"""The paper's bibliography (Plan 4 Task 20): every cited key is present and locatable."""

import re

import pytest

from aideleg.config import ROOT

BIB = ROOT / "docs" / "paper" / "references.bib"

SPEC_KEYS = {
    "acemoglu2019automation",
    "autor2003skill",
    "eloundou2024gpts",
    "felten2021occupational",
    "webb2020impact",
    "eisfeldt2023generative",
    "brynjolfsson2025generative",
    "noy2023experimental",
    "dellacqua2023navigating",
    "dietvorst2015algorithm",
    "logg2019algorithm",
    "parasuraman1997humans",
    "lee2004trust",
    "handa2025economic",
    "fama1993common",
    "fama2015five",
    "fama1973risk",
    "newey1987simple",
    "romano2005stepwise",
    "bailey2014deflated",
    "hassan2019firm",
}
PAP_KEYS = {
    "cameron2011robust",
    "winkler2014permutation",
    "freedman1983nonstochastic",
    "holm1979simple",
    "webb2023reworking",
    "cameron2008bootstrap",
    "carhart1997persistence",
    "newey1994automatic",
    "politis1994stationary",
    "bailey2012sharpe",
}
DATA_KEYS = {
    "anthropic2026economicindex",
    "onet2025database",
    "bls2025oews",
    "french2026datalibrary",
    "sec2026edgar",
    "census2022concordances",
    "bls2018soccrosswalk",
    "aioe2021data",
    "openai2023gptsdata",
}
REQUIRED = SPEC_KEYS | PAP_KEYS | DATA_KEYS

_ENTRY = re.compile(r"^@(\w+)\s*\{\s*([^,\s]+)\s*,", re.MULTILINE)


def _entries() -> dict[str, str]:
    """Map each key to its entry body (the text up to the next entry)."""
    text = BIB.read_text(encoding="utf-8")
    heads = list(_ENTRY.finditer(text))
    out: dict[str, str] = {}
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        key = m.group(2)
        assert key not in out, f"duplicate key {key}"
        out[key] = text[m.end() : end]
    return out


def _field(body: str, name: str) -> str | None:
    m = re.search(rf"^\s*{name}\s*=\s*\{{(.*?)\}}\s*,?\s*$", body, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def test_required_keys_present():
    missing = REQUIRED - set(_entries())
    assert not missing, f"missing keys: {sorted(missing)}"


@pytest.mark.parametrize("key", sorted(REQUIRED))
def test_entries_have_locator(key):
    body = _entries()[key]
    assert _field(body, "doi") or _field(body, "url"), f"{key} has neither doi nor url"


def test_dois_well_formed():
    bad = {
        k: d
        for k, b in _entries().items()
        if (d := _field(b, "doi")) is not None and not re.fullmatch(r"10\.\d{4,9}/\S+", d)
    }
    assert not bad, f"malformed DOIs: {bad}"


def test_every_entry_records_verification_date():
    unverified = [
        k for k, b in _entries().items() if not re.search(r"verified \d{4}-\d{2}-\d{2}", b)
    ]
    assert not unverified, f"no verification note: {unverified}"
