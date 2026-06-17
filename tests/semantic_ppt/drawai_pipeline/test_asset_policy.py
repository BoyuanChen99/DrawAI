from __future__ import annotations

from PIL import Image, ImageDraw

from drawai.asset_policy import (
    analyze_asset_crop,
    decide_asset_policy,
    refine_asset_policy_with_components,
)


def _box(width: int = 120, height: int = 120):
    return {"id": "B001", "type": "icon", "bbox": [0, 0, width, height]}


def test_simple_line_icon_is_native_svg_candidate():
    image = Image.new("RGB", (120, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse([30, 26, 90, 86], outline=(18, 73, 145), width=6)
    draw.line([60, 86, 60, 104], fill=(18, 73, 145), width=6)

    metrics = analyze_asset_crop(image=image, box=_box(), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF01", role="icon", metrics=metrics)

    assert decision.render_policy == "native_svg"
    assert decision.background_policy == "transparent_subject"
    assert decision.should_run_rmbg is False
    assert any(
        reason in decision.reason_codes for reason in ("simple_line_geometry", "simple_low_entropy_geometry")
    )


def test_complex_line_art_on_uniform_background_uses_transparent_png():
    image = Image.new("RGB", (240, 160), "white")
    draw = ImageDraw.Draw(image)
    for index in range(24):
        x = 12 + (index % 8) * 28
        y = 14 + (index // 8) * 44
        draw.ellipse([x, y, x + 12, y + 12], outline=(18, 73, 145), width=2)
        draw.line([x + 6, y + 14, x + 6, y + 24], fill=(18, 73, 145), width=2)

    metrics = analyze_asset_crop(image=image, box=_box(240, 160), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF02", role="icon", metrics=metrics)

    assert decision.render_policy == "raster_png"
    assert decision.background_policy == "transparent_subject"
    assert decision.should_run_rmbg is True
    assert "line_art_on_removable_background" in decision.reason_codes


def test_texture_like_asset_preserves_crop_background():
    image = Image.new("RGB", (128, 128), "white")
    pixels = image.load()
    for y in range(128):
        for x in range(128):
            pixels[x, y] = ((x * 7 + y * 3) % 255, (x * 5) % 255, (y * 11) % 255)

    metrics = analyze_asset_crop(image=image, box=_box(128, 128), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF03", role="picture", metrics=metrics)

    assert decision.render_policy == "raster_png"
    assert decision.background_policy == "preserve_crop"
    assert decision.should_run_rmbg is False
    assert "texture_like" in decision.reason_codes


def test_texture_like_icon_still_preserves_crop_after_component_refine():
    image = Image.new("RGB", (180, 140), "white")
    pixels = image.load()
    for y in range(140):
        for x in range(180):
            pixels[x, y] = ((x * 7 + y * 3) % 255, (x * 5 + y) % 255, (y * 11 + x) % 255)

    metrics = analyze_asset_crop(image=image, box=_box(180, 140), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF06", role="icon", metrics=metrics)
    refined = refine_asset_policy_with_components(decision, ())

    assert refined.render_policy == "raster_png"
    assert refined.background_policy == "preserve_crop"
    assert refined.should_run_rmbg is False
    assert "raster_icon_background_context_preserved" in refined.reason_codes


def test_dense_pixel_like_asset_preserves_crop_background():
    image = Image.new("RGB", (64, 64), (235, 240, 248))
    draw = ImageDraw.Draw(image)
    for y in range(8, 56, 8):
        for x in range(8, 56, 8):
            fill = (18, 73, 145) if (x + y) % 16 == 0 else (80, 120, 190)
            draw.rectangle([x, y, x + 6, y + 6], fill=fill)

    metrics = analyze_asset_crop(image=image, box=_box(64, 64), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF04", role="icon", metrics=metrics)

    assert decision.render_policy == "raster_png"
    assert decision.background_policy == "preserve_crop"
    assert decision.should_run_rmbg is False


def test_backplate_asset_uses_hybrid_policy():
    image = Image.new("RGB", (140, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle([4, 4, 136, 96], radius=18, outline=(18, 73, 145), width=7)
    draw.rectangle([48, 32, 92, 66], outline=(18, 73, 145), width=5)
    draw.line([60, 68, 80, 82], fill=(18, 73, 145), width=5)

    metrics = analyze_asset_crop(image=image, box=_box(140, 100), slide_size=(400, 400))
    decision = decide_asset_policy(asset_id="AF05", role="icon", metrics=metrics)

    assert decision.render_policy == "hybrid"
    assert decision.background_policy == "split_backplate"
    assert decision.should_run_rmbg is True
