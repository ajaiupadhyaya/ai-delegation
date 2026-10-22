"""The single format of PAP section 11 (additions, clarifications, deviations).

Plans 2 to 4 log every data addition, pre-result clarification and deviation through this
module and never write section 11 by hand. Text above `SECTION_11` is never touched.
"""

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from aideleg.config import RAW, ROOT

PAP = ROOT / "docs/pap/pre-analysis-plan.md"
SECTION_11 = "## 11. Deviations"
# in document order; "CP" holds the C entries written after results had been seen (one C series)
SUBSECTIONS = {
    "A": "### Additions (D20)",
    "C": "### Clarifications (pre-result)",
    "CP": "### Clarifications (post-result)",
    "D": "### Deviations after the freeze",
}
POST_RESULT = "(post-result)"
ENTRY_RE = (
    r"^### ([ACD])-(\d+)\. (Addition|Addition \(set\)|Clarification|Deviation): (.+) "
    r"\((\d{4}-\d{2}-\d{2})\)$"
)
_ENTRY = re.compile(ENTRY_RE)
Kind = Literal["A", "C", "D"]
_FORM = {"A": "Addition", "C": "Clarification", "D": "Deviation"}


def section_11_lines(text: str) -> list[str]:
    """The lines of section 11 (heading included), up to the next `## ` heading or the end."""
    lines = text.split("\n")
    if SECTION_11 not in lines:
        raise ValueError(f"{SECTION_11!r} not found")
    start = lines.index(SECTION_11)
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")),
               len(lines))
    return lines[start:end]


def entries(pap: Path = PAP) -> list[dict]:
    """One dict per entry heading in section 11: kind, n, form, title, date, body."""
    lines = section_11_lines(Path(pap).read_text(encoding="utf-8"))
    out: list[dict] = []
    current: dict | None = None
    body: list[str] = []

    def close() -> None:
        if current is not None:
            current["body"] = "\n".join(body).strip("\n")
            out.append(current)

    for line in lines:
        if line.startswith("### "):
            close()
            m = _ENTRY.match(line)
            current = (
                {"kind": m[1], "n": int(m[2]), "form": m[3], "title": m[4], "date": m[5]}
                if m else None
            )
            body = []
        elif current is not None:
            body.append(line)
    close()
    return out


def next_number(kind: Kind, pap: Path = PAP) -> int:
    return 1 + max((e["n"] for e in entries(pap) if e["kind"] == kind), default=0)


def set_digest(pairs: Iterable[tuple[str, str]]) -> str:
    """SHA-256 of the sorted `<key> <sha256>` lines: independent of the order of `pairs`."""
    body = "".join(f"{k} {s}\n" for k, s in sorted(pairs))
    return hashlib.sha256(body.encode()).hexdigest()


# --- entry builders ------------------------------------------------------------------------


def addition(key: str, rec: dict, *, scope: str, used_by: str, date: str,
             pap: Path = PAP) -> str:
    return "\n".join([
        f"### A-{next_number('A', pap)}. Addition: `{key}` ({date})",
        f"- Type: addition under D20 ({scope}; not a deviation)",
        f"- Used by: {used_by}",
        f"- URL: {rec['url']}",
        f"- Retrieved (UTC): {rec['retrieved_utc']}; bytes: {rec['bytes']}; "
        f"SHA-256: `{rec['sha256']}`",
    ])


def set_addition(source: str, *, count: int, digest: str, first_utc: str, last_utc: str,
                 scope: str, used_by: str, date: str, pap: Path = PAP) -> str:
    return "\n".join([
        f"### A-{next_number('A', pap)}. Addition (set): `{source}` ({date})",
        f"- Type: addition under D20 ({scope}; not a deviation)",
        f"- Used by: {used_by}",
        f"- Records: {count}; retrieved (UTC) from {first_utc} to {last_utc}",
        f"- Set digest: `{digest}`",
    ])


def _results_seen(value: str | bool) -> str:
    """The "Results seen" field: free text such as "no", "yes" or "RQ1 confirmatory results
    seen; robustness rows not yet read". A bool is read as yes/no (older callers)."""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if not value.strip() or "\n" in value:
        raise ValueError(f"results_seen must be one non-empty line, not {value!r}")
    return value.strip()


def clarification(title: str, *, rule: str, plan: str, date: str, results_seen: str = "no",
                  pap: Path = PAP) -> str:
    """A C entry. With `results_seen` other than "no" it is a post-result clarification: its Type
    line says so and `append` files it under "Clarifications (post-result)"."""
    seen = _results_seen(results_seen)
    kind = ("- Type: clarification (pre-result); the PAP is silent or ambiguous here and no PAP "
            "rule changes" if seen == "no" else
            f"- Type: clarification {POST_RESULT}; results had been seen; the PAP is silent or "
            "ambiguous here and no PAP rule or confirmatory code changes")
    return "\n".join([
        f"### C-{next_number('C', pap)}. Clarification: {title} ({date})",
        kind,
        f"- Fixed by: {plan}",
        f"- Results seen: {seen}",
        f"- Rule: {rule}",
    ])


def deviation(title: str, *, reason: str, before: str, after: str, results_seen: str | bool,
              approved: str, date: str, pap: Path = PAP) -> str:
    return "\n".join([
        f"### D-{next_number('D', pap)}. Deviation: {title} ({date})",
        "- Type: deviation (needs Ajai's approval; demotion rule of §0.5 if a confirmatory "
        "result was seen)",
        f"- Reason: {reason}",
        f"- Before: {before}",
        f"- After: {after}",
        f"- Results seen: {_results_seen(results_seen)}",
        f"- Approved by Ajai: {approved}",
    ])


# --- writing -------------------------------------------------------------------------------


def _ensure_subsections(text: str) -> str:
    """Create the subsections once; later, insert any missing one in its place in the order."""
    head, _, tail = text.partition(SECTION_11 + "\n")
    if not any(h in tail.split("\n") for h in SUBSECTIONS.values()):
        if not text.endswith("\n"):
            text += "\n"
        return text + "\n" + "\n\n".join(SUBSECTIONS.values()) + "\n"
    lines = text.split("\n")
    order = list(SUBSECTIONS.values())
    for i, h in enumerate(order):
        s11 = lines.index(SECTION_11)
        sec_end = next((j for j in range(s11 + 1, len(lines)) if lines[j].startswith("## ")),
                       len(lines))
        present = {ln: j for j, ln in enumerate(lines[s11:sec_end], s11) if ln in order}
        if h in present:
            continue
        nxt = next((present[g] for g in order[i + 1:] if g in present), None)
        if nxt is not None:
            lines[nxt:nxt] = [h, ""]
        else:
            k = sec_end
            while k > s11 + 1 and lines[k - 1] == "":
                k -= 1
            lines[k:k] = ["", h]
    return "\n".join(lines)


def append(entry: str, pap: Path = PAP) -> None:
    """Insert `entry` at the end of its kind's subsection (creating the subsections once)."""
    pap = Path(pap)
    m = _ENTRY.match(entry.split("\n", 1)[0])
    if m is None:
        raise ValueError("entry heading does not match ENTRY_RE")
    kind, n = m[1], int(m[2])
    section = "CP" if kind == "C" and POST_RESULT in entry.split("\n", 2)[1] else kind
    if n != next_number(kind, pap):  # type: ignore[arg-type]
        raise ValueError(f"entry is numbered {kind}-{n}; the next is "
                         f"{kind}-{next_number(kind, pap)}")  # type: ignore[arg-type]
    text = _ensure_subsections(pap.read_text(encoding="utf-8"))
    lines = text.split("\n")
    s11 = lines.index(SECTION_11)
    sec_end = next((i for i in range(s11 + 1, len(lines)) if lines[i].startswith("## ")),
                   len(lines))
    sub = lines.index(SUBSECTIONS[section], s11, sec_end)
    heads = {i for i in range(sub + 1, sec_end)
             if lines[i] in SUBSECTIONS.values()}
    end = min(heads, default=sec_end)
    while end > sub + 1 and lines[end - 1] == "":
        end -= 1
    block = ["", *entry.rstrip("\n").split("\n")]
    lines[end:end] = block
    # keep one blank line before whatever follows the subsection
    after = end + len(block)
    if after < len(lines) and lines[after] != "":
        lines.insert(after, "")
    elif after >= len(lines):
        lines.append("")
    pap.write_text("\n".join(lines), encoding="utf-8")


# --- manifest coverage ---------------------------------------------------------------------

_SET_RECORDS = re.compile(r"Records: (\d+); retrieved \(UTC\) from (\S+) to (\S+)")
_SET_DIGEST = re.compile(r"Set digest: `([0-9a-f]{64})`")
_SINGLE_SHA = re.compile(r"SHA-256: `([0-9a-f]{64})`")
SET_INDEX_KEY = "sec_docs_index"
SET_INDEX_FILE = "sec/docs/INDEX.jsonl"


def load_manifest(raw_dir: Path = RAW) -> dict[str, dict]:
    return json.loads((Path(raw_dir) / "MANIFEST.json").read_text())


def is_set_source(key: str) -> bool:
    return key.startswith("sec_fts/") or key == SET_INDEX_KEY


def set_entry_fields(entry: dict) -> dict:
    """Parse the count, interval and digest out of a set entry."""
    r, d = _SET_RECORDS.search(entry["body"]), _SET_DIGEST.search(entry["body"])
    if r is None or d is None:
        raise ValueError(f"malformed set entry A-{entry['n']}")
    return {"count": int(r[1]), "first": r[2], "last": r[3], "digest": d[1]}


def set_stats(source: str, manifest: dict[str, dict], raw_dir: Path = RAW, *,
              first: str | None = None, last: str | None = None) -> dict:
    """Count, digest and interval of a set source's records, optionally within [first, last]."""
    if source == SET_INDEX_KEY:
        rec = manifest[SET_INDEX_KEY]
        path = Path(raw_dir) / rec.get("dest", SET_INDEX_FILE)
        count = sum(1 for line in path.read_text().splitlines() if line.strip())
        return {"count": count, "digest": rec["sha256"], "first": rec["retrieved_utc"],
                "last": rec["retrieved_utc"], "keys": [SET_INDEX_KEY]}
    keys = sorted(
        k for k, r in manifest.items()
        if k.startswith(source)
        and (first is None or r["retrieved_utc"] >= first)
        and (last is None or r["retrieved_utc"] <= last)
    )
    stamps = [manifest[k]["retrieved_utc"] for k in keys]
    return {"count": len(keys),
            "digest": set_digest((k, manifest[k]["sha256"]) for k in keys),
            "first": min(stamps, default=""), "last": max(stamps, default=""), "keys": keys}


def _covered_by_set(key: str, rec: dict, set_entries: list[dict]) -> list[dict]:
    out = []
    for e in set_entries:
        f = set_entry_fields(e)
        src = e["title"].strip("`")
        if src == SET_INDEX_KEY:
            hit = key == SET_INDEX_KEY and f["digest"] == rec["sha256"]
        else:
            hit = key.startswith(src) and f["first"] <= rec["retrieved_utc"] <= f["last"]
        if hit:
            out.append(e)
    return out


def uncovered_set_keys(source: str, manifest: dict[str, dict], pap: Path = PAP) -> list[str]:
    """Keys of `source` that no logged set entry covers yet."""
    sets = [e for e in entries(pap) if e["form"] == "Addition (set)"]
    keys = [source] if source == SET_INDEX_KEY else sorted(
        k for k in manifest if k.startswith(source))
    return [k for k in keys if k in manifest and not _covered_by_set(k, manifest[k], sets)]


# --- CLI -----------------------------------------------------------------------------------


def _today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _main_addition(a: argparse.Namespace) -> list[str]:
    manifest = load_manifest(a.raw_dir)
    logged = {e["title"].strip("`") for e in entries(a.pap) if e["form"] == "Addition"}
    out = []
    for key in a.keys:
        if key not in manifest:
            raise SystemExit(f"{key}: not in the MANIFEST")
        if key in logged:
            print(f"skip {key}: already logged")
            continue
        append(addition(key, manifest[key], scope=a.scope, used_by=a.used_by, date=a.date,
                        pap=a.pap), a.pap)
        out.append(key)
    return out


def _main_set_addition(a: argparse.Namespace) -> list[str]:
    manifest = load_manifest(a.raw_dir)
    keys = uncovered_set_keys(a.source, manifest, a.pap)
    if not keys:
        print(f"skip {a.source}: every record is already covered")
        return []
    if a.source == SET_INDEX_KEY:
        s = set_stats(a.source, manifest, a.raw_dir)
    else:
        stamps = [manifest[k]["retrieved_utc"] for k in keys]
        s = set_stats(a.source, manifest, a.raw_dir, first=min(stamps), last=max(stamps))
        if s["keys"] != keys:
            raise SystemExit("uncovered records are not an interval of retrieval times; "
                             "log them by hand through paplog.set_addition")
    append(set_addition(a.source, count=s["count"], digest=s["digest"], first_utc=s["first"],
                        last_utc=s["last"], scope=a.scope, used_by=a.used_by, date=a.date,
                        pap=a.pap), a.pap)
    return [a.source]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aideleg.paplog")
    ap.add_argument("--pap", type=Path, default=PAP)
    ap.add_argument("--raw-dir", type=Path, default=RAW)
    ap.add_argument("--date", default=None, help="entry date (default: today, UTC)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("addition")
    p.add_argument("--keys", nargs="+", required=True, metavar="K")
    p.add_argument("--scope", required=True)
    p.add_argument("--used-by", required=True)
    p = sub.add_parser("set-addition")
    p.add_argument("--source", required=True)
    p.add_argument("--scope", required=True)
    p.add_argument("--used-by", required=True)
    p = sub.add_parser("clarification")
    p.add_argument("--title", required=True)
    p.add_argument("--rule", required=True)
    p.add_argument("--plan", required=True)
    p.add_argument("--results-seen", default="no",
                   help='what results had been seen, e.g. "no" (default), "yes", or "RQ1 '
                        'confirmatory results seen; robustness rows not yet read"')
    p = sub.add_parser("deviation")
    p.add_argument("--title", required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--before", required=True)
    p.add_argument("--after", required=True)
    p.add_argument("--results-seen", required=True,
                   help='"yes", "no", or a one-line description of what was seen')
    p.add_argument("--approved", required=True)
    a = ap.parse_args(argv)
    a.date = a.date or _today()

    if a.cmd == "addition":
        done = _main_addition(a)
    elif a.cmd == "set-addition":
        done = _main_set_addition(a)
    elif a.cmd == "clarification":
        append(clarification(a.title, rule=a.rule, plan=a.plan, date=a.date,
                             results_seen=a.results_seen, pap=a.pap), a.pap)
        done = [a.title]
    else:
        rs = a.results_seen.strip()
        if rs not in ("yes", "no") and "seen" not in rs.lower():
            print(f"warning: --results-seen {rs!r} is neither yes nor no and does not say what "
                  "was seen", file=sys.stderr)
        append(deviation(a.title, reason=a.reason, before=a.before, after=a.after,
                         results_seen=a.results_seen, approved=a.approved,
                         date=a.date, pap=a.pap), a.pap)
        done = [a.title]
    for d in done:
        print(f"logged {d}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
