"""The headline registry and the red-team challenge log (Plan 4 Task 16)."""

import csv
import re

import polars as pl
import pytest

from aideleg import paplog
from aideleg.config import ROOT
from aideleg.paper import headlines as hl

REDTEAM = ROOT / "docs/redteam"
HEADLINES = REDTEAM / "headlines.csv"
CHALLENGES_CSV = REDTEAM / "challenges.csv"
_FIX = re.compile(r"^fix logged as (D-\d+)$")


def _rows(path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _header(path) -> list[str]:
    with open(path, newline="", encoding="utf-8") as f:
        return next(csv.reader(f))


# --- the locator grammar, on fixtures ----------------------------------------------------------


@pytest.fixture
def table(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("h,coef,est,p\nH1,a,0.10,0.5\nH1,b,0.20,0.5\nH2,a,0.30,1e-05\n")
    return p


def _row(path, locator):
    return {"source_file": str(path), "source_locator": locator}


def test_csv_locator_selects_one_cell_as_printed(table):
    assert hl.resolve(_row(table, "csv:h=H1,coef=b:est")) == "0.20"
    assert hl.resolve(_row(table, "csv:h=H2:p")) == "1e-05"


@pytest.mark.parametrize("loc", ["csv:h=H1:est", "csv:h=H9:est", "csv:h=H2:nope", "csv:zz=H2:p"])
def test_csv_locator_refuses_zero_or_many(table, loc):
    with pytest.raises(ValueError):
        hl.resolve(_row(table, loc))


def test_json_locator(tmp_path):
    p = tmp_path / "r.json"
    p.write_text('{"a": {"b": {"c": 0.9274691358024691}}, "l": [1, 2]}')
    assert hl.resolve(_row(p, "json:a.b.c")) == "0.9274691358024691"
    for bad in ("json:a.b", "json:a.x", "json:l"):
        with pytest.raises(ValueError):
            hl.resolve(_row(p, bad))


def test_md_regex_locator(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("| rho | ci |\n|---|---|\n| 0.361 | [0.050, 0.612] |\nrho twice: 1.5 1.5\n")
    assert hl.resolve(_row(p, r"md-regex:^\| (0\.\d+) \| \[")) == "0.361"
    for bad in (r"md-regex:twice: (\d\.\d) (\d\.\d)", r"md-regex:(1\.5)", r"md-regex:(9\.9)"):
        with pytest.raises(ValueError):
            hl.resolve(_row(p, bad))


def test_confirmatory_md_locator_on_the_record():
    rec = ROOT / "docs/results/confirmatory_h5.md"
    assert hl.resolve(_row(rec, "confirmatory_md:H5.b")) == "1.958"
    assert hl.resolve(_row(rec, "confirmatory_md:decision.H5.ci_005.1")) == "6.681"
    mde = r"confirmatory_md:decision.H5.wording~at least (\d+\.\d+) pp per 1 SD"
    assert hl.resolve(_row(rec, mde)) == "7.43"
    for bad in ("confirmatory_md:decision.H5.ci_005", "confirmatory_md:H5.nope"):
        with pytest.raises(ValueError):
            hl.resolve(_row(rec, bad))


def test_unknown_locator_kind(table):
    with pytest.raises(ValueError):
        hl.resolve(_row(table, "xls:A1"))


def test_render_log_lists_every_row():
    df = pl.DataFrame(
        {
            "key": ["rq1.H1.beta_w", "rq1.H1.beta_w"],
            "challenge": ["C1", "C2"],
            "check": ["rebuilt | compared", "read §4.1"],
            "evidence": ["Makefile:1", "pre-analysis-plan.md:697"],
            "outcome": ["holds", "holds"],
            "resolution": ["none needed", "none needed"],
            "commit": ["", ""],
        }
    )
    text = hl.render_log(df)
    assert "rq1.H1.beta_w" in text and "C1 Reproduce" in text and "rebuilt \\| compared" in text
    assert text.count(hl.WORDING) == 1


# --- the committed registry and log ---------------------------------------------------------


def test_headline_keys_resolve():
    assert _header(HEADLINES) == hl.HEADLINE_COLUMNS
    rows = _rows(HEADLINES)
    keys = [r["key"] for r in rows]
    assert len(keys) == len(set(keys)), "duplicate headline keys"
    for r in rows:
        assert (ROOT / r["source_file"]).is_file(), f"{r['key']}: {r['source_file']} missing"
        assert all(r[c] for c in hl.HEADLINE_COLUMNS), f"{r['key']}: an empty column"
        value = hl.resolve(r)
        assert value != "", f"{r['key']}: empty value"


def test_challenges_columns_and_values():
    assert _header(CHALLENGES_CSV) == hl.CHALLENGE_COLUMNS
    for r in _rows(CHALLENGES_CSV):
        assert r["challenge"] in hl.CHALLENGES, r
        assert r["outcome"] in hl.OUTCOMES, r
        assert r["resolution"] in hl.RESOLUTIONS or _FIX.match(r["resolution"]), r


@pytest.mark.xfail(strict=True, reason="filled by the Task 16 review")
def test_every_headline_challenged():
    keys = [r["key"] for r in _rows(HEADLINES)]
    rows = _rows(CHALLENGES_CSV)
    seen: dict[tuple[str, str], int] = {}
    for r in rows:
        seen[(r["key"], r["challenge"])] = seen.get((r["key"], r["challenge"]), 0) + 1
    want = [(k, c) for k in keys for c in hl.CHALLENGES]
    missing = [p for p in want if p not in seen]
    twice = [p for p, n in seen.items() if n > 1]
    extra = [p for p in seen if p not in set(want)]
    empty = [(r["key"], r["challenge"]) for r in rows if not (r["check"] and r["evidence"])]
    assert not (missing or twice or extra or empty), (
        f"{len(missing)} of {len(want)} (key, challenge) pairs missing "
        f"(first: {missing[:3]}); {len(twice)} duplicated; {len(extra)} unknown; "
        f"{len(empty)} with an empty check or evidence"
    )


def test_no_open_failures():
    open_ = [
        (r["key"], r["challenge"])
        for r in _rows(CHALLENGES_CSV)
        if r["outcome"] == "fails" and r["resolution"] == "none needed"
    ]
    assert not open_, f"failing challenges marked 'none needed': {open_}"


def test_stop_rows_block():
    stops = [
        f"{r['key']} {r['challenge']}"
        for r in _rows(CHALLENGES_CSV)
        if r["resolution"] == "STOP: confirmatory issue"
    ]
    assert not stops, f"STOP: confirmatory issue on {stops}"


def test_fixes_have_deviation_entries():
    by_id = {f"{e['kind']}-{e['n']}": e for e in paplog.entries()}
    for r in _rows(CHALLENGES_CSV):
        m = _FIX.match(r["resolution"])
        if not m:
            continue
        ident = m.group(1)
        assert ident in by_id, f"{r['key']} {r['challenge']}: {ident} is not in PAP §11"
        body = by_id[ident]["body"]

        def field(name: str, body: str = body) -> str:
            found = re.search(rf"^- {re.escape(name)}: (.*)$", body, re.M)
            return found.group(1).strip() if found else ""

        assert field("Before"), f"{ident}: empty Before"
        assert field("After"), f"{ident}: empty After"
        # "yes" alone, or "yes: <what was seen>" (D-3)
        seen = field("Results seen")
        assert re.match(r"yes(?::|$)", seen), f"{ident}: Results seen is not yes"
        assert field("Approved by Ajai"), f"{ident}: not approved by Ajai"
