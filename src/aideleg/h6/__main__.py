"""`uv run python -m aideleg.h6 <subcommand>`: the H6 pipeline (exploratory, PAP §6, D18).

- `acquire [--filers] [--fts] [--docs]` is the only network step: `--filers` fetches the EDGAR
  full-index `form.idx` files and the bulk submissions zip, `--fts` the full-text-search numerator
  (one MANIFEST record per response; saved responses are not refetched), `--docs` the 10-K
  documents of the secondary measure (Plan 3 Task 13; until then it says so and does nothing).
  With no flag, all three.
- `build [--filers] [--fts]` is offline: `--filers` writes `data/derived/h6/filers.parquet` from
  the saved files, `--fts` writes `fts_hits.parquet` from the saved responses; with no flag, both.
- `talk`, `secondary`, `summary` are offline, from the derived files; outputs go to
  docs/results/h6/. `secondary` is Plan 3 Task 13; until then it says so and writes nothing.
- `all` = build + talk + secondary + summary, with no acquisition (C-43).
"""

import argparse
import sys
import zipfile

from aideleg.config import RAW, ROOT

OUT_DIR = ROOT / "docs/results/h6"
NOT_YET = "not implemented until Plan 3 Task 13; nothing was done"


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


def acquire(filers: bool, fts: bool, docs: bool) -> None:
    """Network only."""
    from aideleg.acquire import fetch, sources
    from aideleg.h6 import edgar

    if filers:
        for src in sources.SOURCES:
            if src.key.startswith("sec_formidx_") or src.key == "sec_submissions_bulk":
                r = fetch.fetch(src, raw_dir=RAW)
                print(f"{r.key:28} {r.bytes:>12}  {r.sha256[:12]}")
    if fts:
        hits = edgar.acquire_fts()
        print(
            f"{hits.height} hit rows -> {edgar.FTS_HITS.relative_to(ROOT)} "
            "(H6 numerator input, exploratory)"
        )
    if docs:
        print(f"acquire --docs (secondary measure): {NOT_YET}", file=sys.stderr)


def build(filers: bool, fts: bool) -> None:
    """Offline: derived files from saved raw files; never fetches."""
    from aideleg.h6 import edgar

    if filers:
        _print_filers(edgar.build_filers())
    if fts:
        hits = edgar.hits_from_saved()
        edgar.FTS_HITS.parent.mkdir(parents=True, exist_ok=True)
        hits.write_parquet(edgar.FTS_HITS)
        print(
            f"{hits.height} hit rows -> {edgar.FTS_HITS.relative_to(ROOT)} (from saved responses)"
        )


def talk() -> None:
    from aideleg.figures.save import FIGURES_DIR
    from aideleg.h6 import talk as talk_mod

    r = talk_mod.run_talk(OUT_DIR, fig_dir=FIGURES_DIR)
    print(
        f"-> {OUT_DIR.relative_to(ROOT)}/talk_index.md, talk_index.csv, gap.md, gap.csv, "
        "gap_returns.md (exploratory)"
    )
    for p in r["pooled"].iter_rows(named=True):
        print(
            f"  {p['year']} pooled talk={p['talk']:.4f} ({p['n_talk']}/{p['n_filers']}) "
            f"unmapped share={p['unmapped_share']:.4f}"
        )
    sp, g = r["spearman"], r["gap_returns"]
    print(
        f"  Spearman(T, z_usage) = {sp['rho']:.4f} CI=[{sp['ci95'][0]:.4f}, "
        f"{sp['ci95'][1]:.4f}] n={sp['n']} undefined draws={sp['n_nan']}"
    )
    print(
        f"  gap-return b={g['b'] * 100:.3f} pp s={g['s'] * 100:.3f} "
        f"bbar={g['bbar'] * 100:.3f} T_bbar={g['T_bbar']:.3f} p_bbar={g['p_bbar']:.4f} "
        f"T_zero={g['T_zero']:.3f} p_zero={g['p_zero']:.4f} (nominal, no family)"
    )


def secondary() -> None:
    print(f"secondary talk measure: {NOT_YET}", file=sys.stderr)


def summary() -> None:
    from aideleg.h6 import talk as talk_mod

    print(f"-> {talk_mod.write_summary(OUT_DIR).relative_to(ROOT)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aideleg.h6")
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("acquire", help="network acquisitions of H6 inputs")
    a.add_argument("--filers", action="store_true", help="full-index form.idx and submissions")
    a.add_argument("--fts", action="store_true", help="EDGAR full-text search (D18 numerator)")
    a.add_argument("--docs", action="store_true", help="10-K documents (secondary measure)")
    b = sub.add_parser("build", help="build H6 derived files from saved raw files (offline)")
    b.add_argument("--filers", action="store_true", help="the full-index denominator (D18)")
    b.add_argument("--fts", action="store_true", help="the numerator hits from saved responses")
    for name in ("talk", "secondary", "summary", "all"):
        sub.add_parser(name)
    args = p.parse_args(argv)
    if args.command == "acquire":
        flags = (args.filers, args.fts, args.docs)
        acquire(*(flags if any(flags) else (True, True, True)))
    elif args.command == "build":
        flags = (args.filers, args.fts)
        build(*(flags if any(flags) else (True, True)))
    elif args.command == "all":
        # C-43: build + talk + secondary + summary, never acquire
        build(True, True)
        talk()
        secondary()
        summary()
    else:
        {"talk": talk, "secondary": secondary, "summary": summary}[args.command]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
