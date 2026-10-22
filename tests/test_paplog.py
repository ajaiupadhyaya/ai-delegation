import hashlib
import json
import re

import pytest

from aideleg import paplog

FIXTURE = (
    "# Plan\n\n## 10. Something\n\nText with a line.\n\n---\n\n"
    "## 11. Deviations\n\n*None at freeze.*\n\nAny change after the freeze is recorded here.\n"
)
REC = {"url": "u", "retrieved_utc": "t", "bytes": 3, "sha256": "s"}


@pytest.fixture
def pap(tmp_path):
    p = tmp_path / "pap.md"
    p.write_text(FIXTURE, encoding="utf-8")
    return p


def _c(pap, title="t", n_date="2026-10-22"):
    return paplog.clarification(title, rule="r", plan="p", date=n_date, pap=pap)


def test_append_creates_subsections_in_order(pap):
    paplog.append(_c(pap), pap)
    text = pap.read_text(encoding="utf-8")
    assert text.startswith(FIXTURE)
    i = [text.index(h) for h in paplog.SUBSECTIONS.values()]
    assert i == sorted(i)
    c = text.index("### C-1.")
    assert text.index(paplog.SUBSECTIONS["C"]) < c < text.index(paplog.SUBSECTIONS["D"])
    assert text.endswith("\n") and not text.endswith("\n\n")
    paplog.append(_c(pap, "second").replace("C-1", "C-2"), pap)
    assert [e["n"] for e in paplog.entries(pap)] == [1, 2]
    # the subsections are not created twice
    assert pap.read_text(encoding="utf-8").count(paplog.SUBSECTIONS["A"]) == 1


def test_entries_inserted_at_end_of_their_own_subsection(pap):
    paplog.append(_c(pap), pap)
    paplog.append(paplog.addition("k", REC, scope="s", used_by="x", date="2026-10-22",
                                  pap=pap), pap)
    paplog.append(paplog.addition("k2", REC, scope="s", used_by="x", date="2026-10-22",
                                  pap=pap), pap)
    text = pap.read_text(encoding="utf-8")
    assert (text.index("### A-1.") < text.index("### A-2.")
            < text.index(paplog.SUBSECTIONS["C"]) < text.index("### C-1."))
    assert [e["title"] for e in paplog.entries(pap)] == ["`k`", "`k2`", "t"]


def test_entry_formats_exact(pap):
    a = paplog.addition("k", REC, scope="outside §9.4; descriptive", used_by="x",
                        date="2026-10-22", pap=pap)
    assert a == "\n".join([
        "### A-1. Addition: `k` (2026-10-22)",
        "- Type: addition under D20 (outside §9.4; descriptive; not a deviation)",
        "- Used by: x",
        "- URL: u",
        "- Retrieved (UTC): t; bytes: 3; SHA-256: `s`",
    ])
    s = paplog.set_addition("sec_fts/", count=4, digest="d", first_utc="a", last_utc="b",
                            scope="pre-specified in §9.4", used_by="y", date="2026-10-22",
                            pap=pap)
    assert s == "\n".join([
        "### A-1. Addition (set): `sec_fts/` (2026-10-22)",
        "- Type: addition under D20 (pre-specified in §9.4; not a deviation)",
        "- Used by: y",
        "- Records: 4; retrieved (UTC) from a to b",
        "- Set digest: `d`",
    ])
    c = paplog.clarification("Title", rule="R", plan="Plan 2 Task 4", date="2026-10-22", pap=pap)
    assert c == "\n".join([
        "### C-1. Clarification: Title (2026-10-22)",
        "- Type: clarification (pre-result); the PAP is silent or ambiguous here and no PAP "
        "rule changes",
        "- Fixed by: Plan 2 Task 4",
        "- Results seen: no",
        "- Rule: R",
    ])
    d = paplog.deviation("T", reason="why", before="b", after="a", results_seen=True,
                         approved="yes, 2026-10-22", date="2026-10-22", pap=pap)
    assert d == "\n".join([
        "### D-1. Deviation: T (2026-10-22)",
        "- Type: deviation (needs Ajai's approval; demotion rule of §0.5 if a confirmatory "
        "result was seen)",
        "- Reason: why",
        "- Before: b",
        "- After: a",
        "- Results seen: yes",
        "- Approved by Ajai: yes, 2026-10-22",
    ])
    for block in (a, s, c, d):
        assert re.match(paplog.ENTRY_RE, block.split("\n")[0])
    for h in paplog.SUBSECTIONS.values():
        assert not re.match(paplog.ENTRY_RE, h)


def test_numbering_per_kind(pap):
    for key in ("a", "b"):
        paplog.append(paplog.addition(key, REC, scope="s", used_by="x", date="2026-10-22",
                                      pap=pap), pap)
    paplog.append(_c(pap), pap)
    assert (paplog.next_number("A", pap), paplog.next_number("C", pap),
            paplog.next_number("D", pap)) == (3, 2, 1)
    bad = paplog.addition("z", REC, scope="s", used_by="x", date="2026-10-22",
                          pap=pap).replace("A-3", "A-5")
    before = pap.read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        paplog.append(bad, pap)
    assert pap.read_text(encoding="utf-8") == before


def test_set_digest_order_free():
    want = hashlib.sha256(b"a 1\nb 2\n").hexdigest()
    assert paplog.set_digest([("b", "2"), ("a", "1")]) == want
    assert paplog.set_digest([("a", "1"), ("b", "2")]) == want


def _raw(tmp_path, manifest):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "MANIFEST.json").write_text(json.dumps(manifest))
    return raw


def test_cli_addition_idempotent(pap, tmp_path):
    raw = _raw(tmp_path, {"k": {**REC, "key": "k", "dest": "d"}})
    argv = ["--pap", str(pap), "--raw-dir", str(raw), "--date", "2026-10-22",
            "addition", "--keys", "k", "--scope", "outside §9.4; descriptive",
            "--used-by", "x"]
    assert paplog.main(argv) == 0
    assert paplog.main(argv) == 0
    es = [e for e in paplog.entries(pap) if e["kind"] == "A"]
    assert [e["title"] for e in es] == ["`k`"]


def test_cli_set_addition_logs_only_uncovered_records(pap, tmp_path):
    def rec(t, s):
        return {**REC, "retrieved_utc": t, "sha256": s * 64}
    man = {"sec_fts/1": rec("2026-11-01T00:00:00Z", "1"),
           "sec_fts/2": rec("2026-11-02T00:00:00Z", "2")}
    raw = _raw(tmp_path, man)
    argv = ["--pap", str(pap), "--raw-dir", str(raw), "--date", "2026-11-03",
            "set-addition", "--source", "sec_fts/", "--scope", "s", "--used-by", "x"]
    assert paplog.main(argv) == 0
    assert paplog.main(argv) == 0  # nothing new: no second entry
    [e] = paplog.entries(pap)
    f = paplog.set_entry_fields(e)
    assert f["count"] == 2
    assert f["digest"] == paplog.set_digest((k, v["sha256"]) for k, v in man.items())
    man["sec_fts/3"] = rec("2026-11-05T00:00:00Z", "3")
    (raw / "MANIFEST.json").write_text(json.dumps(man))
    assert paplog.main(argv) == 0
    second = paplog.set_entry_fields(paplog.entries(pap)[1])
    assert second["count"] == 1 and second["first"] == "2026-11-05T00:00:00Z"


def test_cli_set_addition_for_the_docs_index(pap, tmp_path):
    raw = _raw(tmp_path, {"sec_docs_index": {**REC, "dest": "sec/docs/INDEX.jsonl",
                                             "sha256": "e" * 64}})
    (raw / "sec/docs").mkdir(parents=True)
    (raw / "sec/docs/INDEX.jsonl").write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n')
    assert paplog.main(["--pap", str(pap), "--raw-dir", str(raw), "--date", "2026-11-03",
                        "set-addition", "--source", "sec_docs_index", "--scope", "s",
                        "--used-by", "x"]) == 0
    f = paplog.set_entry_fields(paplog.entries(pap)[0])
    assert f["count"] == 3 and f["digest"] == "e" * 64


def test_results_seen_field_is_explicit(pap):
    c = paplog.clarification("T", rule="R", plan="P", date="2026-10-22", pap=pap,
                             results_seen="RQ1 confirmatory results seen")
    assert "- Results seen: RQ1 confirmatory results seen" in c.split("\n")
    assert "- Results seen: no" in _c(pap).split("\n")  # default keeps old callers working
    d = paplog.deviation("T", reason="w", before="b", after="a", approved="y",
                         date="2026-10-22", pap=pap,
                         results_seen="RQ1 confirmatory results seen; robustness rows not read")
    assert "- Results seen: RQ1 confirmatory results seen; robustness rows not read" in d
    for bad in ("", "  ", "two\nlines"):
        with pytest.raises(ValueError):
            paplog.clarification("T", rule="R", plan="P", date="d", pap=pap, results_seen=bad)


def test_cli_results_seen(pap):
    base = ["--pap", str(pap), "--date", "2026-10-22", "clarification", "--title", "A",
            "--rule", "r", "--plan", "p"]
    assert paplog.main(base) == 0
    assert paplog.main([*base[:-6], "--title", "B", "--rule", "r", "--plan", "p",
                        "--results-seen", "yes"]) == 0
    seen = [ln for e in paplog.entries(pap) for ln in e["body"].split("\n")
            if ln.startswith("- Results seen:")]
    assert seen == ["- Results seen: no", "- Results seen: yes"]


POST_TYPE = ("- Type: clarification (post-result); results had been seen; the PAP is silent or "
             "ambiguous here and no PAP rule or confirmatory code changes")


def test_post_result_clarification_type_and_subsection(pap):
    assert list(paplog.SUBSECTIONS) == ["A", "C", "CP", "D"]
    assert paplog.SUBSECTIONS["CP"] == "### Clarifications (post-result)"
    paplog.append(_c(pap, "pre"), pap)
    post = paplog.clarification("post", rule="r", plan="p", date="2026-10-22", pap=pap,
                                results_seen="RQ1 confirmatory results seen")
    assert POST_TYPE in post.split("\n")
    assert "(pre-result)" not in post
    paplog.append(post, pap)
    paplog.append(_c(pap, "pre again"), pap)  # numbering stays one C series
    paplog.append(paplog.deviation("d", reason="w", before="b", after="a", results_seen="no",
                                   approved="y", date="2026-10-22", pap=pap), pap)
    text = pap.read_text(encoding="utf-8")
    h = paplog.SUBSECTIONS
    assert (text.index(h["C"]) < text.index("### C-1.") < text.index("### C-3.")
            < text.index(h["CP"]) < text.index("### C-2.") < text.index(h["D"])
            < text.index("### D-1."))
    assert [(e["kind"], e["n"]) for e in paplog.entries(pap)] == [
        ("C", 1), ("C", 3), ("C", 2), ("D", 1)]
    assert text.count(h["CP"]) == 1


def test_missing_subsection_is_inserted_in_order(pap):
    old = "\n\n".join(paplog.SUBSECTIONS[k] for k in ("A", "C", "D"))
    pap.write_text(FIXTURE + "\n" + old.replace(paplog.SUBSECTIONS["D"],
                   "### C-1. Clarification: x (2026-10-22)\n- Rule: r\n\n"
                   + paplog.SUBSECTIONS["D"]) + "\n", encoding="utf-8")
    paplog.append(paplog.clarification("post", rule="r", plan="p", date="2026-10-22", pap=pap,
                                       results_seen="yes"), pap)
    text = pap.read_text(encoding="utf-8")
    i = [text.index(h) for h in paplog.SUBSECTIONS.values()]
    assert i == sorted(i)
    assert text.index("### C-1.") < text.index(paplog.SUBSECTIONS["CP"]) < text.index("### C-2.")
    assert "\n\n\n" not in text


def test_deviation_cli_warns_on_unclear_results_seen(pap, capsys):
    base = ["--pap", str(pap), "--date", "2026-10-22", "deviation", "--title", "T",
            "--reason", "r", "--before", "b", "--after", "a", "--approved", "y"]
    assert paplog.main([*base, "--results-seen", "maybe"]) == 0
    assert "warning" in capsys.readouterr().err.lower()
    for ok in ("yes", "no", "RQ1 confirmatory results seen"):
        paplog.main([*base[:5], "--title", ok, *base[7:], "--results-seen", ok])
        assert capsys.readouterr().err == ""
