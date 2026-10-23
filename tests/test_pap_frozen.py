import json
import re
import subprocess

from aideleg import paplog
from aideleg.config import PAP_TAG, RAW, ROOT


def _git_show(path: str) -> str:
    return subprocess.run(["git", "show", f"{PAP_TAG}:{path}"], cwd=ROOT, check=True,
                          capture_output=True, text=True).stdout


def test_pap_unchanged_outside_section_11():
    frozen = _git_show("docs/pap/pre-analysis-plan.md")
    now = paplog.PAP.read_text(encoding="utf-8")
    assert now.startswith(frozen)
    rest = now[len(frozen):].lstrip()
    assert rest == "" or rest.startswith(tuple(paplog.SUBSECTIONS.values()))


def test_every_addition_logged():
    manifest = paplog.load_manifest(RAW)
    new = set(manifest) - set(json.loads(_git_show("data/raw/MANIFEST.json")))
    es = [e for e in paplog.entries() if e["kind"] == "A"]
    singles = [e for e in es if e["form"] == "Addition"]
    sets = [e for e in es if e["form"] == "Addition (set)"]
    for key in sorted(new):
        if paplog.is_set_source(key):
            hits = paplog._covered_by_set(key, manifest[key], sets)
            assert len(hits) == 1, f"{key}: covered by {len(hits)} set entries"
        else:
            hits = [e for e in singles if e["title"] == f"`{key}`"]
            assert len(hits) == 1, f"{key}: covered by {len(hits)} entries"
            logged = re.search(r"SHA-256: `([0-9a-f]{64})`", hits[0]["body"])
            assert logged and logged[1] == manifest[key]["sha256"], key
    # The index-file set is one MANIFEST record, so only its latest entry can match the
    # current file; an earlier one is the superseded state it records (A-34 -> A-35).
    index_entries = [e for e in sets if e["title"].strip("`") == paplog.SET_INDEX_KEY]
    superseded = {e["n"] for e in index_entries[:-1]}
    for e in sets:
        if e["n"] in superseded:
            continue
        f = paplog.set_entry_fields(e)
        s = paplog.set_stats(e["title"].strip("`"), manifest, RAW,
                             first=f["first"], last=f["last"])
        assert (s["count"], s["digest"]) == (f["count"], f["digest"]), e["title"]


def test_section_11_entries_well_formed():
    headings = [ln for ln in paplog.section_11_lines(paplog.PAP.read_text(encoding="utf-8"))
                if ln.startswith("### ")]
    subs = set(paplog.SUBSECTIONS.values())
    for h in headings:
        assert h in subs or re.match(paplog.ENTRY_RE, h), h
    for kind in "ACD":
        ns = [e["n"] for e in paplog.entries() if e["kind"] == kind]
        assert ns == list(range(1, len(ns) + 1)), f"{kind}: {ns}"
