"""Write a figure as PDF + PNG, byte-reproducibly, and close it."""

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

from matplotlib.figure import Figure  # noqa: E402

from aideleg.config import ROOT  # noqa: E402

FIGURES_DIR = ROOT / "docs/paper/figures"
_NAME = re.compile(r"^[a-z0-9][a-z0-9_]*$")


def save_figure(fig: Figure, name: str, *, out_dir: Path = FIGURES_DIR) -> tuple[Path, Path]:
    """Save `<name>.pdf` and `<name>.png` into `out_dir`, then close the figure."""
    import matplotlib.pyplot as plt

    try:
        if not _NAME.fullmatch(name):
            raise ValueError(f"figure name {name!r} must match {_NAME.pattern}")
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf, png = out_dir / f"{name}.pdf", out_dir / f"{name}.png"
        fig.savefig(pdf, metadata={"CreationDate": None, "Creator": "aideleg"})
        fig.savefig(png, metadata={"Software": "aideleg"})
    finally:
        plt.close(fig)
    return pdf, png
