"""One colour-blind-safe style for every figure in the paper and the results documents."""

import matplotlib as mpl
from cycler import cycler

# Okabe-Ito colour-blind-safe set
PALETTE: tuple[str, ...] = (
    "#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7",
)
SEQUENTIAL_CMAP = "viridis"
DIVERGING_CMAP = "PuOr"
MISSING_COLOR = "#D9D9D9"

# inches
FIGSIZE: dict[str, tuple[float, float]] = {
    "single": (3.5, 2.6),
    "double": (7.0, 4.2),
    "map": (7.0, 3.8),
    "tall": (7.0, 8.0),
}

FONT_FAMILY = "DejaVu Sans"  # ships with matplotlib, so renders are deterministic
BASE_FONTSIZE = 8


def apply_style() -> None:
    """Set the shared rcParams. Calling it twice is harmless."""
    mpl.rcParams.update({
        "font.family": [FONT_FAMILY],
        "font.size": BASE_FONTSIZE,
        "axes.prop_cycle": cycler(color=list(PALETTE)),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.hashsalt": "aideleg",
        "figure.dpi": 100,
    })
