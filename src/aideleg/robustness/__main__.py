"""`python -m aideleg.robustness [--only R01 R17 ...] [--offline]`: run the listed PAP §8.2 rows,
or every Plan 4 row that has a runner, in registry order. Row names are accepted as `R1` or `R01`.
`--summary` writes only the appendix (`summary.md`, `implementation_choices.md`) and the two
forest figures from the committed row files. `--diagnostics` writes only the post-result
influence diagnostics of PAP §11 D-3 (`docs/results/diagnostics/`). `--offline` sets
`rows.OFFLINE`: the H6 rows never fetch, and saved full-text-search responses that do not cover
a request raise instead."""

import argparse
import sys
import time

from aideleg.robustness import registry, rows


def _resolve(names: list[str]) -> list[str]:
    by_stem = {registry.output_stem(rid): rid for rid in registry.ROWS}
    out = []
    for n in names:
        rid = n if n in registry.ROWS else by_stem.get(n)
        if rid is None:
            raise SystemExit(f"unknown row {n!r}")
        if rid not in rows.RUNNERS:
            raise SystemExit(f"row {n!r} has no Plan 4 runner")
        out.append(rid)
    return [rid for rid in registry.ROWS if rid in out]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="python -m aideleg.robustness")
    ap.add_argument("--only", nargs="+", metavar="ROW", help="rows to run, e.g. R01 R17")
    ap.add_argument("--offline", action="store_true", help="never fetch; use saved responses only")
    ap.add_argument(
        "--summary", action="store_true", help="write the appendix and figures; run no row"
    )
    ap.add_argument(
        "--diagnostics",
        action="store_true",
        help="write the PAP §11 D-3 influence diagnostics; run no row",
    )
    args = ap.parse_args(argv)
    if args.diagnostics:
        from aideleg.robustness import diagnostics

        for path in diagnostics.write_all():
            print(path, flush=True)
        return
    if args.summary:
        from aideleg.robustness import appendix, figures

        for path in (*appendix.write_appendix(), *figures.write_figures()):
            print(path, flush=True)
        return
    rows.OFFLINE = args.offline
    ids = _resolve(args.only) if args.only else [r for r in registry.ROWS if r in rows.RUNNERS]
    for rid in ids:
        t0 = time.perf_counter()
        csv, md = rows.RUNNERS[rid]()
        print(f"{rid}: {csv} {md} ({time.perf_counter() - t0:.1f}s)", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
