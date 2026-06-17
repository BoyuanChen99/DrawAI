from pathlib import Path

from PIL import Image


def test_demo_figure_is_a_valid_png():
    path = Path("examples/demo_figure.png")

    assert path.is_file()
    with Image.open(path) as image:
        assert image.format == "PNG"
        assert image.size == (1200, 800)
