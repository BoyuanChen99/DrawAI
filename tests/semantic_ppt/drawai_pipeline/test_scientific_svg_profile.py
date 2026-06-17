from pathlib import Path

from PIL import Image

from drawai.scientific_svg_profile import (
    validate_scientific_svg_profile,
)


def test_scientific_svg_profile_rejects_blocked_browser_features(tmp_path: Path):
    svg = tmp_path / "blocked.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80" width="100" height="80">
  <defs>
    <filter id="shadow"><feDropShadow dx="2" dy="2" stdDeviation="1"/></filter>
    <clipPath id="clip"><rect width="20" height="20"/></clipPath>
    <mask id="mask"><rect width="20" height="20" fill="white"/></mask>
    <pattern id="dots" width="4" height="4" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1"/></pattern>
  </defs>
  <rect id="panel" width="40" height="20" filter="url(#shadow)" fill="url(#dots)"/>
  <g clip-path="url(#clip)" mask="url(#mask)"><foreignObject width="10" height="10"/></g>
  <text><textPath href="#curve">label</textPath></text>
</svg>""",
        encoding="utf-8",
    )

    report = validate_scientific_svg_profile(svg)

    assert report["profile"] == "DrawAI Scientific SVG Profile v1"
    assert report["compliant"] is False
    assert report["uses_filter"] is True
    assert report["uses_mask"] is True
    assert report["uses_clipPath"] is True
    assert report["uses_foreignObject"] is True
    assert report["uses_pattern"] is True
    codes = {violation["code"] for violation in report["violations"]}
    assert {
        "blocked_filter",
        "blocked_clipPath",
        "blocked_mask",
        "blocked_foreignObject",
        "blocked_textPath",
        "risky_pattern",
    }.issubset(codes)


def test_scientific_svg_profile_rejects_base64_and_whole_slide_images(tmp_path: Path):
    svg = tmp_path / "bad_image.svg"
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80" width="100" height="80">
  <image id="screenshot" href="data:image/png;base64,AAAA" x="0" y="0" width="100" height="80"/>
</svg>""",
        encoding="utf-8",
    )

    report = validate_scientific_svg_profile(svg)

    assert report["compliant"] is False
    codes = {violation["code"] for violation in report["violations"]}
    assert "base64_image" in codes
    assert "whole_slide_image" in codes


def test_scientific_svg_profile_accepts_manifest_raster_asset_and_reports_roles(tmp_path: Path):
    asset = tmp_path / "assets" / "AF01.png"
    asset.parent.mkdir()
    Image.new("RGB", (8, 8), "red").save(asset)
    svg = tmp_path / "svg" / "semantic.svg"
    svg.parent.mkdir()
    svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80" width="100" height="80">
  <rect id="background" data-pb-role="background" width="100" height="80" fill="#fff"/>
  <g id="panel_1" data-pb-role="panel" data-pb-editable="true">
    <rect x="5" y="5" width="40" height="20" fill="none" stroke="#111"/>
    <text id="label_1" data-pb-role="label" x="10" y="20">Label</text>
  </g>
  <image id="AF01" data-pb-role="image" data-pb-editable="false" data-asset-id="AF01"
         href="../assets/AF01.png" x="60" y="10" width="8" height="8"/>
</svg>""",
        encoding="utf-8",
    )

    report = validate_scientific_svg_profile(
        svg,
        asset_manifest={"assets": [{"asset_id": "AF01", "svg_href": "../assets/AF01.png"}]},
    )

    assert report["compliant"] is True
    assert report["violations"] == []
    assert report["has_semantic_roles"] is True
    assert report["role_counts"]["panel"] == 1
    assert report["role_counts"]["image"] == 1
