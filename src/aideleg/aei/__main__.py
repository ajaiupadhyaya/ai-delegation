"""`python -m aideleg.aei`: build the AEI panel and write its quality report."""

import sys

from aideleg.aei.panel import build_panel, check_panel
from aideleg.config import ROOT

REPORT = ROOT / "docs/audit/tables/panel_quality.md"


def main() -> int:
    df = build_panel()
    rep = check_panel(df)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(rep.to_markdown())
    print(f"{df.height} rows -> data/derived/aei_panel.parquet; report {REPORT}")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
