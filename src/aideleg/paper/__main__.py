"""`uv run python -m aideleg.paper`: regenerate `docs/paper/_variables.yml` and the table and
figure includes under `docs/paper/_generated/` from the committed results (Plan 4 Task 18), and the
five appendix includes under `docs/paper/_generated/appendix/` (Task 21).
Offline; reads committed files, git metadata and, where present, the raw `INDEX.jsonl` (whose
line count the data appendix checks against PAP §11)."""

import sys

from aideleg.paper import includes, variables


def _count(d: dict) -> int:
    return sum(_count(v) if isinstance(v, dict) else 1 for v in d.values())


def main() -> int:
    vars_ = variables.build()
    variables.write(vars_)
    tables = includes.build_tables()
    figures = includes.build_figures()
    appendices = includes.build_appendices()
    print(
        f"{variables.OUT.relative_to(variables.ROOT)}: {_count(vars_)} variables; "
        f"{len(tables)} table includes; {len(figures)} figure includes; "
        f"{len(appendices)} appendix includes"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
