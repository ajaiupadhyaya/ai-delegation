"""Rebuild the generated block of `docs/pap/power.md` (Task 33, T-2), after the freeze too.

`python -m aideleg.power` refuses once the tag `pap-v1` exists, because the frozen values must
not be re-chosen. `make all` still rebuilds the block, so the fresh-clone check compares a
rebuilt power.md with the committed one instead of the committed bytes with themselves. This
calls the unedited `aideleg.power.run_power`, which reads French returns only up to
2022-11-29 (pre-seal) and the Design B exposure vector; the text outside the block is kept.
A rebuilt block that differs from the committed one is a replication difference, reported by
`scripts/compare_outputs.py`, never committed.
"""

import sys

from aideleg import power
from aideleg.config import ROOT


def main() -> int:
    before = power.OUT.read_text() if power.OUT.exists() else None
    power.run_power()
    after = power.OUT.read_text()
    same = "reproduced byte for byte" if after == before else "DIFFERS from the committed file"
    print(f"{power.OUT.relative_to(ROOT)}: generated block rebuilt; {same}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
