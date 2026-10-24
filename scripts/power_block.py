"""Rebuild the generated block of `docs/pap/power.md` (Task 33, T-2) and compare it with the
committed one, after the freeze too. Exit 1 on any difference.

`python -m aideleg.power` refuses once the tag `pap-v1` exists, because the frozen values must
not be re-chosen. `make all` still rebuilds the block, so the fresh-clone check compares a
rebuilt block with the committed one instead of the committed bytes with themselves. This
calls the unedited `aideleg.power.run_power`, which reads French returns only up to
2022-11-29 (pre-seal) and the Design B exposure vector, with `out` set to a temporary copy of
the committed file: the frozen `docs/pap/power.md` itself is never written. A rebuilt block
that differs from the committed one is a replication difference, reported here, never
committed.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from aideleg import power
from aideleg.config import ROOT


def main() -> int:
    committed = power.OUT.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="aideleg-power-") as tmp:
        rebuilt_path = Path(tmp) / power.OUT.name
        shutil.copyfile(power.OUT, rebuilt_path)
        power.run_power(out=rebuilt_path)
        rebuilt = rebuilt_path.read_text(encoding="utf-8")
    rel = power.OUT.relative_to(ROOT)
    if rebuilt == committed:
        print(f"{rel}: generated block rebuilt in a temporary copy; reproduced byte for byte")
        return 0
    print(f"{rel}: generated block rebuilt in a temporary copy; DIFFERS from the committed file")
    return 1


if __name__ == "__main__":
    sys.exit(main())
