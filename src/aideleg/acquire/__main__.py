"""`uv run python -m aideleg.acquire [--only KEY ...]`: fetch the registry and print a summary.

`--from-dir DIR` seeds the raw directory from a frozen archive instead (offline; every file is
verified against the committed MANIFEST, and the 10-K documents against INDEX.jsonl), and
`--check-download` downloads every non-bulk MANIFEST file into a temporary directory and writes
`docs/replication/download_check.md` without touching `data/raw` (`aideleg.acquire.seed`).
"""

import argparse
import sys
from pathlib import Path

from aideleg.acquire import fetch, seed, sources
from aideleg.config import RAW


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aideleg.acquire")
    ap.add_argument("--only", nargs="+", metavar="KEY", help="fetch only these keys")
    ap.add_argument("--force", action="store_true", help="download again even if current")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--from-dir", metavar="DIR", type=Path,
                      help="copy every MANIFEST file from DIR/<dest>, verified (offline)")
    mode.add_argument("--check-download", action="store_true",
                      help="re-download into a temporary directory and report matches")
    ap.add_argument("--raw-dir", type=Path, default=RAW, help=argparse.SUPPRESS)  # tests
    args = ap.parse_args(argv)

    if args.from_dir is not None:
        refused = seed.from_dir(args.from_dir, raw_dir=args.raw_dir)
        for key, reason in refused:
            print(f"REFUSED {key}: {reason}", file=sys.stderr)
        if refused:
            print(f"\n{len(refused)} refused; nothing was written for them", file=sys.stderr)
            return 1
        return 0
    if args.check_download:
        rows = seed.check_download(raw_dir=args.raw_dir)
        bad = [r["key"] for r in rows if r["match"] != "yes"]
        print(f"{len(rows) - len(bad)} of {len(rows)} match -> {seed.DOWNLOAD_CHECK}")
        if bad:
            print(f"differ: {', '.join(bad)}")
        return 0

    if args.only:
        unknown = [k for k in args.only if k not in {s.key for s in sources.SOURCES}]
        if unknown:
            ap.error(f"unknown keys: {', '.join(unknown)}")
        chosen = [sources.by_key(k) for k in args.only]
    else:
        chosen = sources.SOURCES

    records, failures = [], []
    for src in chosen:
        try:
            records.append(fetch.fetch(src, raw_dir=RAW, force=args.force))
        except fetch.FetchError as exc:
            failures.append((src.key, str(exc)))
            print(f"FAILED {src.key}: {exc}", file=sys.stderr)

    print(f"{'key':28} {'bytes':>12}  sha256")
    for r in records:
        print(f"{r.key:28} {r.bytes:>12}  {r.sha256[:12]}")
    if failures:
        print(f"\n{len(failures)} failed: {', '.join(k for k, _ in failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
