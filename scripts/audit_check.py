"""Rebuild the data-audit coverage tables (`docs/audit/tables/`, PAP: "the audit") into a
temporary directory and compare every table `aideleg.audit.build` writes with the committed one
(Task 33, T-2). Exit 1 on any difference, or on a rebuilt table that is not committed. (The other
files in that directory are not `aideleg.audit`'s: `panel_quality.md` is written with the panel
by `python -m aideleg.aei`.)

The audit tables are frozen inputs of the PAP, so `make all` never rewrites them in place: it
calls the unedited `aideleg.audit.build` with `out` set to a temporary directory and compares
byte for byte. `make audit` still writes them in place, for a deliberate rebuild.
"""

import sys
import tempfile
from pathlib import Path

from aideleg import audit
from aideleg.config import ROOT


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="aideleg-audit-") as tmp:
        written = audit.build(out=Path(tmp))
        rebuilt = {p.name: p.read_bytes() for p in written}
    rel = audit.TABLES.relative_to(ROOT)
    bad = 0
    for name in sorted(rebuilt):
        committed = audit.TABLES / name
        if not committed.is_file():
            status = "rebuilt only, not committed"
        elif rebuilt[name] == committed.read_bytes():
            status = "reproduced byte for byte"
        else:
            status = "DIFFERS from the committed file"
        bad += status != "reproduced byte for byte"
        print(f"{rel}/{name}: {status}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
