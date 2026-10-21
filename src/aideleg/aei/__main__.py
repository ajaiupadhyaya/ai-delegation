"""`python -m aideleg.aei`: build the AEI panel and write its quality report."""

import sys

from aideleg.aei.panel import build_panel, check_panel, write_panel
from aideleg.config import DERIVED, ROOT

REPORT = ROOT / "docs/audit/tables/panel_quality.md"
PANEL = DERIVED / "aei_panel.parquet"


def main() -> int:
    df = build_panel(write=False)
    rep = check_panel(df)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(rep.to_markdown())
    if not rep.ok:
        PANEL.unlink(missing_ok=True)  # a stale panel must not survive a failed rebuild
        print(f"quality checks FAILED, panel not written (any old one removed); report {REPORT}")
        return 1
    write_panel(df)
    print(f"{df.height} rows -> data/derived/aei_panel.parquet; report {REPORT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
