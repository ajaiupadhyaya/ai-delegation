import matplotlib.pyplot as plt
import pytest
from PIL import Image

from aideleg.figures import FIGSIZE, apply_style, save_figure


def _fig():
    apply_style()
    fig, ax = plt.subplots(figsize=FIGSIZE["single"])
    ax.plot([0, 1, 2], [1, 3, 2])
    return fig


def test_save_writes_pdf_and_png(tmp_path):
    pdf, png = save_figure(_fig(), "demo", out_dir=tmp_path)
    assert pdf == tmp_path / "demo.pdf" and pdf.exists()
    assert png == tmp_path / "demo.png" and png.exists()
    assert Image.open(png).width == round(3.5 * 300)


def test_save_is_byte_reproducible(tmp_path):
    a, _ = save_figure(_fig(), "a", out_dir=tmp_path)
    b, _ = save_figure(_fig(), "b", out_dir=tmp_path)
    assert a.read_bytes() == b.read_bytes()


def test_save_closes_the_figure(tmp_path):
    fig = _fig()
    save_figure(fig, "c", out_dir=tmp_path)
    assert not plt.fignum_exists(fig.number)


@pytest.mark.parametrize("name", ["a/b", "Fig 1", "x.pdf"])
def test_save_rejects_bad_names(tmp_path, name):
    with pytest.raises(ValueError):
        save_figure(_fig(), name, out_dir=tmp_path)
    plt.close("all")


def test_save_closes_the_figure_when_the_name_is_rejected(tmp_path):
    fig = _fig()
    with pytest.raises(ValueError):
        save_figure(fig, "Bad Name", out_dir=tmp_path)
    assert not plt.fignum_exists(fig.number)
