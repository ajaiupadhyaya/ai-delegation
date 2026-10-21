"""`uv run python -m aideleg.acquire [--only KEY ...]`: fetch the registry and print a summary."""

import argparse
import sys

from aideleg.acquire import fetch, sources
from aideleg.config import RAW


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="aideleg.acquire")
    ap.add_argument("--only", nargs="+", metavar="KEY", help="fetch only these keys")
    ap.add_argument("--force", action="store_true", help="download again even if current")
    args = ap.parse_args(argv)

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
