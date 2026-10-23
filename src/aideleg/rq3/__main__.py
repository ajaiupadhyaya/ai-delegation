"""`uv run python -m aideleg.rq3 <subcommand>`; outputs go to docs/results/rq3/."""

import argparse
import sys

from aideleg.config import ROOT

OUT_DIR = ROOT / "docs/results/rq3"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m aideleg.rq3")
    p.add_argument("command", choices=["influence"])
    args = p.parse_args(argv)
    if args.command == "influence":
        from aideleg.rq3 import inference

        df = inference.main_influence(OUT_DIR)
        print(f"{df.height} rows -> {(OUT_DIR / 'influence.md').relative_to(ROOT)}, "
              f"{(OUT_DIR / 'influence.csv').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
