"""`uv run python -m aideleg.h6 <subcommand>`: the H6 pipeline (exploratory, PAP §6).

`build --filers` builds `data/derived/h6/filers.parquet` from saved raw files (no network)
and prints the 10-K filers and unmapped CIKs per year. Acquisition is separate
(`python -m aideleg.acquire`), except `acquire --fts`: the EDGAR full-text-search numerator
(network; one MANIFEST record per response; resumable, saved responses are not refetched),
written to `data/derived/h6/fts_hits.parquet`.
"""

import argparse
import sys
import zipfile

from aideleg.config import RAW, ROOT


def _print_filers(df) -> None:
    from aideleg.acquire.sources import by_key
    from aideleg.h6 import edgar

    print(f"{df.height} filings -> {edgar.FILERS.relative_to(ROOT)} (H6 denominator, exploratory)")
    with zipfile.ZipFile(RAW / by_key("sec_submissions_bulk").dest) as zf:
        missing = set(edgar.missing_from_zip(df["cik"].unique(), zf))
    for r in edgar.unmapped_report(df).iter_rows(named=True):
        n_missing = df.filter(df["year"] == r["year"])["cik"].unique().is_in(list(missing)).sum()
        print(
            f"  {r['year']}  filers={r['n_filers']:>5}  unmapped={r['n_unmapped']:>4}  "
            f"(no SIC={r['n_no_sic']:>4}, of which not in submissions.zip={n_missing:>4}; "
            f"SIC outside Siccodes49={r['n_sic_outside']:>4})"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aideleg.h6")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="build H6 derived files from saved raw files")
    b.add_argument("--filers", action="store_true", help="the full-index denominator (D18)")
    a = sub.add_parser("acquire", help="network acquisitions of H6 inputs")
    a.add_argument("--fts", action="store_true", help="EDGAR full-text search (D18 numerator)")
    args = p.parse_args(argv)
    if args.command == "acquire":
        if not args.fts:
            p.error("acquire: name what to acquire (--fts)")
        from aideleg.h6 import edgar

        hits = edgar.acquire_fts()
        print(
            f"{hits.height} hit rows -> {edgar.FTS_HITS.relative_to(ROOT)} "
            "(H6 numerator input, exploratory)"
        )
    if args.command == "build":
        parts = [k for k in ("filers",) if getattr(args, k)] or ["filers"]
        if "filers" in parts:
            from aideleg.h6 import edgar

            _print_filers(edgar.build_filers())
    return 0


if __name__ == "__main__":
    sys.exit(main())
