import matplotlib as mpl

from aideleg.figures import style

OKABE_ITO = ("#000000", "#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")


def test_palette_is_okabe_ito():
    assert style.PALETTE == OKABE_ITO


def test_apply_style_sets_rcparams():
    style.apply_style()
    style.apply_style()  # idempotent
    assert mpl.rcParams["pdf.fonttype"] == 42
    assert mpl.rcParams["ps.fonttype"] == 42
    assert mpl.rcParams["font.family"] == ["DejaVu Sans"]
    assert mpl.rcParams["font.size"] == style.BASE_FONTSIZE
    assert mpl.rcParams["axes.prop_cycle"].by_key()["color"][0] == "#000000"
    assert not mpl.rcParams["axes.spines.top"]
    assert not mpl.rcParams["axes.spines.right"]
    assert mpl.rcParams["savefig.dpi"] == 300
    assert mpl.rcParams["svg.hashsalt"] == "aideleg"
    assert mpl.rcParams["figure.dpi"] == 100
