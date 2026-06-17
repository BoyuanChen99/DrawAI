from pathlib import Path

from PIL import Image, ImageColor

from drawai.overlays import render_semantic_overlay


def test_render_semantic_overlay_writes_png(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (120, 80), "white").save(image_path)
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 120, "height": 80},
        "boxes": [{"id": "B001", "type": "arrow", "bbox": [10, 10, 50, 30], "score": 0.9}],
        "ocr_text_boxes": [{"id": "T001", "bbox": [60, 10, 100, 30], "confidence": 0.7, "source": "fixture"}],
    }
    out = tmp_path / "overlay.png"
    legend = render_semantic_overlay(image_path, box_ir, out)
    assert out.exists()
    assert legend["colors"]["arrow"]
    assert Image.open(out).size == (120, 80)


def test_render_semantic_overlay_keeps_interior_pixels_unfilled(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (120, 80), "white").save(image_path)
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 120, "height": 80},
        "boxes": [{"id": "B001", "type": "content_box", "bbox": [10, 10, 90, 60], "score": 0.9}],
        "ocr_text_boxes": [],
    }
    out = tmp_path / "overlay.png"

    legend = render_semantic_overlay(image_path, box_ir, out)
    overlay = Image.open(out).convert("RGB")

    assert set(legend["colors"]) == {
        "arrow",
        "border",
        "content_box",
        "grid",
        "symbol",
        "icon",
        "picture",
        "text",
        "unknown",
    }
    assert overlay.getpixel((50, 40)) == (255, 255, 255)
    assert overlay.getpixel((10, 10)) != (255, 255, 255)


def test_render_semantic_overlay_can_disable_labels(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (120, 80), "white").save(image_path)
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 120, "height": 80},
        "boxes": [{"id": "B001", "type": "arrow", "bbox": [10, 10, 60, 40], "score": 0.9}],
        "ocr_text_boxes": [],
    }
    out = tmp_path / "overlay.png"

    render_semantic_overlay(image_path, box_ir, out, draw_labels=False)
    overlay = Image.open(out).convert("RGB")

    assert overlay.getpixel((13, 13)) == (255, 255, 255)
    assert overlay.getpixel((10, 10)) != (255, 255, 255)


def test_render_semantic_overlay_can_draw_color_legend(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (320, 220), "white").save(image_path)
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 320, "height": 220},
        "boxes": [{"id": "B001", "type": "arrow", "bbox": [180, 120, 260, 170], "score": 0.9}],
        "ocr_text_boxes": [{"id": "T001", "bbox": [190, 20, 260, 40], "text": "Label"}],
    }
    out = tmp_path / "overlay_legend.png"

    legend = render_semantic_overlay(image_path, box_ir, out, draw_legend=True)
    overlay = Image.open(out).convert("RGB")

    assert legend["legend_drawn"] is True
    assert legend["colors"]["text"]
    assert overlay.getpixel((12, 12)) != (255, 255, 255)


def test_render_semantic_overlay_draws_icon_outline_above_content_box(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    Image.new("RGB", (120, 80), "white").save(image_path)
    box_ir = {
        "schema": "drawai.box_ir.v1",
        "canvas": {"width": 120, "height": 80},
        "boxes": [
            {"id": "B001", "type": "icon", "bbox": [10, 10, 60, 60], "score": 0.9},
            {"id": "B002", "type": "content_box", "bbox": [10, 10, 60, 60], "score": 0.8},
        ],
        "ocr_text_boxes": [],
    }
    out = tmp_path / "overlay.png"

    render_semantic_overlay(image_path, box_ir, out, draw_labels=False)
    overlay = Image.open(out).convert("RGB")

    assert overlay.getpixel((10, 10)) == ImageColor.getrgb("#00acc1")
