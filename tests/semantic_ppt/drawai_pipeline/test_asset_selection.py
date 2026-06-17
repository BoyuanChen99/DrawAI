from pathlib import Path

import pytest
from PIL import Image

from drawai.asset_materialization import materialize_assets, materialize_run0_refined_assets
from drawai.rmbg_client import RmbgResult
from drawai.asset_selection_loop import (
    AssetSelectionError,
    apply_svg_recoverability_to_asset_decisions,
    build_initial_asset_decisions,
    validate_asset_decisions,
)
from drawai.overlays import render_visual_template_reference


BOX_IR = {
    "canvas": {"width": 100, "height": 80},
    "boxes": [
        {"id": "B001", "type": "icon", "bbox": [10, 10, 40, 40]},
        {"id": "B002", "type": "arrow", "bbox": [50, 10, 90, 20]},
    ],
    "ocr_text_boxes": [],
}


def test_asset_validator_rejects_arrow_crop():
    decisions = {"decisions": [{"box_id": "B002", "decision": "crop_asset", "asset_id": "AF01"}]}
    issues = validate_asset_decisions(
        BOX_IR,
        decisions,
        disallow_crop_roles={"arrow"},
        max_area_ratio=0.35,
    )
    assert any("B002" in issue and "arrow" in issue for issue in issues)


def test_materialize_assets_crops_from_figure(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}
    manifest = materialize_assets(image, BOX_IR, decisions, tmp_path / "assets")
    asset = manifest["assets"][0]
    assert asset["svg_href"] == "../assets/crops/AF01.png"
    assert "path" not in asset
    assert not any(Path(str(value)).is_absolute() for value in asset.values() if isinstance(value, str))
    crop_path = tmp_path / "assets" / "crops" / "AF01.png"
    assert crop_path.exists()
    assert Image.open(crop_path).size == (30, 30)


def test_materialize_assets_uses_cleaned_without_background_asset_when_rmbg_enabled(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    class FakeRmbgClient:
        def __init__(self):
            self.calls = []

        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            self.calls.append(
                {
                    "size": crop.size,
                    "output_name": output_name,
                    "timeout_s": timeout_s,
                    "model_path": model_path,
                    "artifact_prefix": artifact_prefix,
                }
            )
            rgba = crop.convert("RGBA")
            rgba.putalpha(128)
            return RmbgResult(
                image=rgba,
                artifacts={"nobg": "/v1/segment/artifacts/rmbg/icon_AF01_nobg.png"},
                elapsed_ms=12.5,
            )

    fake_client = FakeRmbgClient()

    manifest = materialize_assets(
        image,
        BOX_IR,
        decisions,
        tmp_path / "assets",
        rmbg_config={
            "enabled": True,
            "timeout_seconds": 7,
            "model_path": "/opt/drawai/models/rmbg",
        },
        rmbg_client=fake_client,
    )

    crop_path = tmp_path / "assets" / "crops" / "AF01.png"
    nobg_path = tmp_path / "assets" / "crops" / "AF01_nobg.png"
    assert crop_path.exists()
    assert nobg_path.exists()
    assert Image.open(crop_path).mode == "RGB"
    assert Image.open(nobg_path).mode == "RGBA"
    assert fake_client.calls == [
        {
            "size": (30, 30),
            "output_name": "AF01",
            "timeout_s": 7,
            "model_path": "/opt/drawai/models/rmbg",
            "artifact_prefix": "drawai_assets/AF01",
        }
    ]

    asset = manifest["assets"][0]
    assert asset["source_svg_href"] == "../assets/crops/AF01.png"
    assert asset["svg_href"] == "../assets/crops/AF01_nobg.png"
    assert asset["nobg_svg_href"] == "../assets/crops/AF01_nobg.png"
    assert asset["active_variant"] == "without_background"
    assert "variants" not in asset
    assert asset["rmbg_elapsed_ms"] == 12.5
    assert asset["rmbg_artifacts"] == {"nobg": "/v1/segment/artifacts/rmbg/icon_AF01_nobg.png"}


def test_materialize_run0_refined_assets_uses_refined_bbox_and_category(tmp_path: Path):
    image = tmp_path / "figure.png"
    canvas = Image.new("RGB", (100, 80), "white")
    for x in range(20, 45):
        for y in range(15, 35):
            canvas.putpixel((x, y), (10, 120, 200))
    canvas.save(image)

    class FakeRmbgClient:
        def __init__(self):
            self.calls = []

        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            self.calls.append({"size": crop.size, "output_name": output_name})
            rgba = crop.convert("RGBA")
            rgba.putalpha(128)
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=1.5)

    fake_client = FakeRmbgClient()
    manifest = materialize_run0_refined_assets(
        image,
        {
            "schema": "drawai.codex_element_analysis.v1",
            "elements": [
                {
                    "box_id": "B001",
                    "source_candidate_ids": ["B001"],
                    "refinement_action": "adjusted",
                    "category": "crop_nobg",
                    "confidence": "high",
                    "visual_role": "icon",
                    "reason": "foreground icon",
                    "bbox": [20, 15, 45, 35],
                    "type": "icon",
                },
                {
                    "box_id": "B002",
                    "category": "svg_self_draw",
                    "bbox": [50, 10, 80, 30],
                },
            ],
        },
        tmp_path / "svg_to_ppt" / "assets",
        rmbg_config={"enabled": True, "timeout_seconds": 5, "model_path": "m"},
        rmbg_client=fake_client,
    )

    assert manifest["source"] == "codex_run0_refined_assets"
    assert manifest["asset_count"] == 1
    asset = manifest["assets"][0]
    assert asset["asset_id"] == "R0_B001"
    assert asset["bbox"] == [20, 15, 45, 35]
    assert asset["source_candidate_ids"] == ["B001"]
    assert asset["active_variant"] == "without_background"
    assert asset["svg_href"] == "../svg_to_ppt/assets/crops/run0_refined/R0_B001_nobg.png"
    assert fake_client.calls == [{"size": (25, 20), "output_name": "R0_B001"}]
    assert (tmp_path / "svg_to_ppt" / "assets" / "crops" / "run0_refined" / "R0_B001.png").exists()
    assert (tmp_path / "svg_to_ppt" / "assets" / "crops" / "run0_refined" / "R0_B001_nobg.png").exists()


def test_materialize_assets_policy_can_activate_without_background_variant(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    class FakeRmbgClient:
        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            rgba = crop.convert("RGBA")
            rgba.putalpha(128)
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=3.0)

    manifest = materialize_assets(
        image,
        BOX_IR,
        decisions,
        tmp_path / "assets",
        rmbg_config={"enabled": True},
        rmbg_client=FakeRmbgClient(),
        asset_policy_report={
            "schema": "drawai.asset_policy_report.v1",
            "assets": [
                {
                    "asset_id": "AF01",
                    "render_policy": "raster_png",
                    "background_policy": "transparent_subject",
                    "split_policy": "no_split",
                    "confidence": "medium",
                    "current_label": "PNG-T",
                    "should_run_rmbg": True,
                    "reason_codes": ["line_art_on_removable_background"],
                    "components": [],
                }
            ],
        },
    )

    asset = manifest["assets"][0]
    assert asset["svg_href"] == "../assets/crops/AF01_nobg.png"
    assert asset["active_variant"] == "without_background"
    assert asset["background_policy"] == "transparent_subject"
    assert asset["policy_reason_codes"] == ["line_art_on_removable_background"]


def test_materialize_assets_cleans_edge_connected_pale_cutout_background(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    class FakeRmbgClient:
        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            rgba = Image.new("RGBA", crop.size, (247, 250, 245, 255))
            for x in range(8, 22):
                rgba.putpixel((x, 15), (40, 55, 60, 255))
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=1.0)

    materialize_assets(
        image,
        BOX_IR,
        decisions,
        tmp_path / "assets",
        rmbg_config={"enabled": True},
        rmbg_client=FakeRmbgClient(),
    )

    nobg = Image.open(tmp_path / "assets" / "crops" / "AF01_nobg.png").convert("RGBA")
    assert nobg.getpixel((0, 0))[3] == 0
    assert nobg.getpixel((10, 15))[3] == 255


def test_materialize_assets_component_split_writes_insertable_component_not_parent(tmp_path: Path):
    image = tmp_path / "figure.png"
    canvas = Image.new("RGB", (100, 80), "white")
    for x in range(30, 40):
        for y in range(15, 30):
            canvas.putpixel((x, y), (255, 80, 0))
    canvas.save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    class FakeRmbgClient:
        def __init__(self):
            self.calls = []

        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            self.calls.append({"size": crop.size, "output_name": output_name, "artifact_prefix": artifact_prefix})
            rgba = crop.convert("RGBA")
            rgba.putalpha(128)
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=2.0)

    fake_client = FakeRmbgClient()

    manifest = materialize_assets(
        image,
        BOX_IR,
        decisions,
        tmp_path / "assets",
        rmbg_config={"enabled": True},
        rmbg_client=fake_client,
        asset_policy_report={
            "schema": "drawai.asset_policy_report.v1",
            "assets": [
                {
                    "asset_id": "AF01",
                    "render_policy": "hybrid",
                    "background_policy": "split_backplate",
                    "split_policy": "safe_compound_split",
                    "confidence": "medium",
                    "current_label": "COMBO",
                    "should_run_rmbg": True,
                    "reason_codes": ["compound_safe_split"],
                    "components": [
                        {
                            "kind": "svg_geometry",
                            "bbox": [0, 0, 30, 30],
                            "confidence": "medium",
                            "source": "test",
                        },
                        {
                            "kind": "raster_symbol_transparent",
                            "bbox": [20, 5, 30, 20],
                            "confidence": "medium",
                            "source": "test",
                            "reason_codes": ["warm_saturated_local_component"],
                        },
                    ],
                }
            ],
        },
    )

    asset = manifest["assets"][0]
    assert asset["insertable"] is False
    assert asset["restore_strategy"] == "component_assets"
    assert "svg_href" not in asset
    assert asset["source_svg_href"] == "../assets/crops/AF01.png"
    assert "nobg_svg_href" not in asset
    assert fake_client.calls == [
        {
            "size": (10, 15),
            "output_name": "AF01_C01",
            "artifact_prefix": "drawai_assets/AF01_C01",
        }
    ]

    component = asset["insertable_components"][0]
    assert component["component_id"] == "AF01_C01"
    assert component["parent_asset_id"] == "AF01"
    assert component["bbox"] == [30, 15, 40, 30]
    assert component["local_bbox"] == [20, 5, 30, 20]
    assert component["svg_href"] == "../assets/crops/AF01_C01_nobg.png"
    assert component["active_variant"] == "without_background"
    assert (tmp_path / "assets" / "crops" / "AF01_C01.png").exists()
    assert (tmp_path / "assets" / "crops" / "AF01_C01_nobg.png").exists()


def test_materialize_assets_policy_preserve_crop_still_uses_transparent_asset_when_rmbg_enabled(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    class FakeRmbgClient:
        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            rgba = crop.convert("RGBA")
            rgba.putalpha(128)
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=1.0)

    manifest = materialize_assets(
        image,
        BOX_IR,
        decisions,
        tmp_path / "assets",
        rmbg_config={"enabled": True},
        rmbg_client=FakeRmbgClient(),
        asset_policy_report={
            "schema": "drawai.asset_policy_report.v1",
            "assets": [
                {
                    "asset_id": "AF01",
                    "render_policy": "raster_png",
                    "background_policy": "preserve_crop",
                    "split_policy": "no_split",
                    "confidence": "high",
                    "current_label": "PNG-O",
                    "should_run_rmbg": False,
                    "reason_codes": ["texture_like"],
                    "components": [],
                }
            ],
        },
    )

    asset = manifest["assets"][0]
    assert asset["source_svg_href"] == "../assets/crops/AF01.png"
    assert asset["svg_href"] == "../assets/crops/AF01_nobg.png"
    assert asset["active_variant"] == "without_background"
    assert asset["nobg_svg_href"] == "../assets/crops/AF01_nobg.png"


def test_visual_template_reference_masks_component_bbox_for_compound_asset(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}
    output = tmp_path / "reference.png"

    render_visual_template_reference(
        image,
        BOX_IR,
        decisions,
        output,
        draw_labels=False,
        asset_policy_report={
            "schema": "drawai.asset_policy_report.v1",
            "assets": [
                {
                    "asset_id": "AF01",
                    "render_policy": "hybrid",
                    "background_policy": "split_backplate",
                    "split_policy": "safe_compound_split",
                    "components": [
                        {"kind": "svg_geometry", "bbox": [0, 0, 30, 30]},
                        {"kind": "raster_symbol_transparent", "bbox": [20, 5, 30, 20]},
                    ],
                }
            ],
        },
    )

    rendered = Image.open(output).convert("RGB")
    assert rendered.getpixel((15, 15)) == (255, 255, 255)
    assert rendered.getpixel((35, 20)) == (128, 128, 128)


def test_materialize_assets_uses_ppt_local_asset_paths_for_tool(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    manifest = materialize_assets(image, BOX_IR, decisions, tmp_path / "svg_to_ppt" / "assets")

    asset = manifest["assets"][0]
    assert asset["svg_href"] == "../svg_to_ppt/assets/crops/AF01.png"
    crop_path = tmp_path / "svg_to_ppt" / "assets" / "crops" / "AF01.png"
    assert crop_path.exists()


def test_materialize_assets_rejects_direct_arrow_crop(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B002", "decision": "crop_asset", "asset_id": "AF01"}]}

    with pytest.raises(AssetSelectionError, match="B002.*arrow"):
        materialize_assets(image, BOX_IR, decisions, tmp_path / "assets")

    assert not (tmp_path / "assets" / "asset_manifest.json").exists()
    assert not (tmp_path / "assets" / "crops" / "AF01.png").exists()


def test_asset_validator_rejects_duplicate_asset_ids():
    decisions = {
        "decisions": [
            {"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"},
            {"box_id": "B002", "decision": "native_svg", "asset_id": "AF01"},
        ]
    }

    issues = validate_asset_decisions(BOX_IR, decisions, disallow_crop_roles=set(), max_area_ratio=1.0)

    assert any("Duplicate asset_id" in issue and "AF01" in issue for issue in issues)


def test_materialize_assets_rejects_duplicate_asset_ids(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    box_ir = {
        "canvas": {"width": 100, "height": 80},
        "boxes": [
            {"id": "B001", "type": "icon", "bbox": [10, 10, 30, 30]},
            {"id": "B002", "type": "icon", "bbox": [40, 10, 60, 30]},
        ],
        "ocr_text_boxes": [],
    }
    decisions = {
        "decisions": [
            {"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"},
            {"box_id": "B002", "decision": "crop_asset", "asset_id": "AF01"},
        ]
    }

    with pytest.raises(AssetSelectionError, match="Duplicate asset_id"):
        materialize_assets(image, box_ir, decisions, tmp_path / "assets")


def test_initial_asset_decisions_gray_box_all_icon_photo_and_figure_roles():
    box_ir = {
        "canvas": {"width": 200, "height": 120},
        "boxes": [
            {"id": "B001", "type": "icon", "bbox": [10, 10, 30, 30]},
            {"id": "B002", "type": "photo", "bbox": [40, 10, 70, 40]},
            {"id": "B003", "type": "figure", "bbox": [80, 10, 110, 40]},
            {"id": "B004", "type": "arrow", "bbox": [120, 10, 180, 20]},
            {"id": "B005", "type": "content_box", "bbox": [5, 5, 190, 100]},
        ],
        "ocr_text_boxes": [],
    }

    decisions = build_initial_asset_decisions(box_ir)

    assert decisions["schema"] == "drawai.asset_decisions.v1"
    assert decisions["decisions"] == [
        {"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01", "initial_crop_role": "icon"},
        {"box_id": "B002", "decision": "crop_asset", "asset_id": "AF02", "initial_crop_role": "picture"},
        {"box_id": "B003", "decision": "crop_asset", "asset_id": "AF03", "initial_crop_role": "picture"},
        {"box_id": "B004", "decision": "native_svg"},
        {"box_id": "B005", "decision": "native_svg"},
    ]


def test_apply_svg_recoverability_cancels_gray_box_ids_locally():
    initial_decisions = {
        "schema": "drawai.asset_decisions.v1",
        "decisions": [
            {"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01", "initial_crop_role": "icon"},
            {"box_id": "B002", "decision": "crop_asset", "asset_id": "AF02", "initial_crop_role": "picture"},
            {"box_id": "B003", "decision": "native_svg"},
        ],
    }
    recovery = {"schema": "drawai.svg_recoverable_assets.v1", "recoverable_asset_ids": ["AF01"]}

    final_decisions = apply_svg_recoverability_to_asset_decisions(initial_decisions, recovery)

    assert final_decisions["decisions"] == [
        {
            "box_id": "B001",
            "decision": "native_svg",
            "recovered_asset_id": "AF01",
            "recovery_reason": "asset_policy",
        },
        {"box_id": "B002", "decision": "crop_asset", "asset_id": "AF02", "initial_crop_role": "picture"},
        {"box_id": "B003", "decision": "native_svg"},
    ]


def test_asset_validator_rejects_unknown_box_id():
    decisions = {"decisions": [{"box_id": "B999", "decision": "crop_asset", "asset_id": "AF01"}]}

    issues = validate_asset_decisions(BOX_IR, decisions, disallow_crop_roles=set(), max_area_ratio=0.35)

    assert any("Unknown box_id" in issue and "B999" in issue for issue in issues)


def test_asset_validator_rejects_ocr_box_crop():
    box_ir = {
        "canvas": {"width": 100, "height": 80},
        "boxes": [{"id": "B001", "type": "icon", "bbox": [10, 10, 40, 40]}],
        "ocr_text_boxes": [{"id": "T001", "bbox": [12, 12, 35, 20], "text": "Label"}],
    }
    decisions = {"decisions": [{"box_id": "T001", "decision": "crop_asset", "asset_id": "AF01"}]}

    issues = validate_asset_decisions(box_ir, decisions, disallow_crop_roles=set(), max_area_ratio=0.35)

    assert any("OCR text box" in issue and "T001" in issue for issue in issues)


def test_asset_validator_rejects_area_ratio_over_threshold():
    box_ir = {
        "canvas": {"width": 100, "height": 80},
        "boxes": [{"id": "B001", "type": "picture", "bbox": [0, 0, 80, 50]}],
        "ocr_text_boxes": [],
    }
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}

    issues = validate_asset_decisions(box_ir, decisions, disallow_crop_roles=set(), max_area_ratio=0.35)

    assert any("area ratio" in issue and "B001" in issue for issue in issues)


def test_visual_template_reference_draws_only_labeled_gray_asset_boxes(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    box_ir = {
        "canvas": {"width": 100, "height": 80},
        "boxes": [
            {"id": "B001", "type": "icon", "bbox": [10, 10, 40, 40]},
            {"id": "B002", "type": "arrow", "bbox": [50, 10, 90, 30]},
        ],
        "ocr_text_boxes": [{"id": "T001", "bbox": [10, 50, 60, 70], "text": "Label"}],
    }
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}
    out = tmp_path / "template_reference.png"

    legend = render_visual_template_reference(image, box_ir, decisions, out)
    rendered = Image.open(out).convert("RGB")

    assert legend["schema"] == "drawai.box_ir.visual_template_reference_legend.v1"
    assert legend["asset_fill"] == "#808080"
    assert legend["asset_border"] is None
    assert legend["assets"]["AF01"]["box_id"] == "B001"
    assert legend["assets"]["AF01"]["border"] is None
    assert rendered.getpixel((12, 12)) == (128, 128, 128)
    assert rendered.getpixel((10, 10)) == (128, 128, 128)
    assert rendered.getpixel((50, 10)) == (255, 255, 255)
    assert rendered.getpixel((10, 50)) == (255, 255, 255)


def test_visual_template_reference_can_overlay_content_box_segmentation(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    box_ir = {
        "canvas": {"width": 100, "height": 80},
        "boxes": [
            {"id": "B001", "type": "icon", "bbox": [10, 10, 40, 40]},
            {"id": "B002", "type": "content_box", "bbox": [45, 45, 95, 75]},
        ],
        "ocr_text_boxes": [],
    }
    decisions = {"decisions": [{"box_id": "B001", "decision": "crop_asset", "asset_id": "AF01"}]}
    out = tmp_path / "template_reference.png"

    legend = render_visual_template_reference(image, box_ir, decisions, out, semantic_types=("content_box",))
    rendered = Image.open(out).convert("RGB")

    assert legend["semantic_fills"]["content_box"]["fill"] == "#43a047"
    assert rendered.getpixel((50, 50)) != (255, 255, 255)
    assert rendered.getpixel((45, 45)) != (67, 160, 71)
    assert rendered.getpixel((12, 12)) == (128, 128, 128)


def test_materialize_assets_handles_no_assets(tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (100, 80), "white").save(image)
    decisions = {"decisions": [{"box_id": "B001", "decision": "native_svg"}]}

    manifest = materialize_assets(image, BOX_IR, decisions, tmp_path / "assets")

    assert manifest == {"schema": "drawai.asset_manifest.v1", "assets": []}
    assert (tmp_path / "assets" / "asset_manifest.json").exists()
