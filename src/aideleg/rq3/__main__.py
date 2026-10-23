"""`uv run python -m aideleg.rq3 <subcommand>`; outputs go to docs/results/rq3/."""

import argparse
import sys

from aideleg.config import ROOT

OUT_DIR = ROOT / "docs/results/rq3"


def _print_events(df) -> None:
    print(f"{df.height} rows -> {(OUT_DIR / 'event_study.md').relative_to(ROOT)}, "
          "event_study.csv, event_days.csv, eisfeldt_replication.md (exploratory)")
    for r in df.iter_rows(named=True):
        print(f"  {r['event']:<11} k={r['horizon']:>2} {str(r['design']):<8} "
              f"{r['regressors']:<20} {r['regressor']:<12} b={r['b']:8.3f} "
              f"CI=[{r['ci_lo']:8.3f}, {r['ci_hi']:8.3f}] p={r['p']:.4f} n={r['n']}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aideleg.rq3")
    p.add_argument("command", choices=["influence", "events"])
    args = p.parse_args(argv)
    if args.command == "influence":
        from aideleg.rq3 import inference

        df = inference.main_influence(OUT_DIR)
        print(f"{df.height} rows -> {(OUT_DIR / 'influence.md').relative_to(ROOT)}, "
              f"{(OUT_DIR / 'influence.csv').relative_to(ROOT)}")
    elif args.command == "events":
        from aideleg.figures.save import FIGURES_DIR
        from aideleg.rq3 import events

        df = events.run_events(OUT_DIR, fig_dir=FIGURES_DIR)
        _print_events(df)
    return 0


if __name__ == "__main__":
    sys.exit(main())
