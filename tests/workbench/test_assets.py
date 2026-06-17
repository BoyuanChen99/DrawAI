from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from drawai.rmbg_client import RmbgResult
from drawai.workbench.assets import (
    approve_asset_plan,
    draft_from_run0_analysis,
    materialize_approved_assets,
    process_asset_plan_elements,
    validate_asset_plan,
    workbench_dir,
    write_asset_draft,
)


def test_draft_from_run0_analysis_and_approve_materializes_crop(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    (case_dir / "inputs").mkdir(parents=True)
    (case_dir / "reports" / "element_analysis_codex").mkdir(parents=True)
    Image.new("RGB", (20, 20), "white").save(case_dir / "inputs" / "figure.png")
    Image.new("RGB", (20, 20), "white").save(case_dir / "inputs" / "original.png")
    _write_json(
        case_dir / "reports" / "element_analysis_codex" / "element_analysis.json",
        {
            "schema": "drawai.codex_element_analysis.v1",
            "elements": [
                {
                    "box_id": "B001",
                    "source_candidate_ids": ["B001"],
                    "bbox": [1, 2, 9, 10],
                    "category": "crop",
                    "type": "image",
                    "visual_role": "dense inset",
                    "confidence": "high",
                },
                {
                    "box_id": "B002",
                    "source_candidate_ids": ["B002"],
                    "bbox": [10, 2, 18, 8],
                    "category": "svg_self_draw",
                    "type": "arrow",
                },
            ],
        },
    )

    draft = draft_from_run0_analysis(case_dir, case_id="case_1")
    assert draft["categories"] == {"crop": 1, "svg_self_draw": 1}
    assert draft["elements"][0]["source_strategy"] == "crop"

    draft_path = write_asset_draft(case_dir, draft)
    assert draft_path == workbench_dir(case_dir) / "asset_draft.json"

    approved = approve_asset_plan(case_dir)
    assert approved["elements"][0]["source_strategy"] == "crop"

    manifest = materialize_approved_assets(case_dir)
    assert manifest["source"] == "codex_run0_refined_assets"
    assert manifest["asset_count"] == 1
    crop_path = case_dir / "svg_to_ppt" / "assets" / "crops" / "run0_refined" / "R0_B001.png"
    assert crop_path.exists()


def test_validate_asset_plan_rejects_bad_strategy_and_degenerate_bbox() -> None:
    with pytest.raises(ValueError, match="Unknown source strategy"):
        validate_asset_plan(
            {
                "elements": [
                    {
                        "box_id": "B001",
                        "bbox": [0, 0, 1, 1],
                        "source_strategy": "photo_magic",
                    }
                ]
            }
        )

    with pytest.raises(ValueError, match="positive area"):
        validate_asset_plan(
            {
                "elements": [
                    {
                        "box_id": "B001",
                        "bbox": [0, 0, 0, 1],
                        "source_strategy": "crop",
                    }
                ]
            }
        )


def test_process_asset_plan_elements_writes_real_nobg_result(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    (case_dir / "inputs").mkdir(parents=True)
    source = Image.new("RGBA", (12, 12), (255, 255, 255, 255))
    for x in range(3, 9):
        for y in range(3, 9):
            source.putpixel((x, y), (20, 120, 220, 255))
    source.save(case_dir / "inputs" / "figure.png")
    plan = {
        "schema": "drawai.workbench_asset_plan.v1",
        "case_id": "case_1",
        "elements": [
            {
                "box_id": "A001",
                "bbox": [2, 2, 10, 10],
                "source_strategy": "crop_nobg",
                "type": "image",
            }
        ],
    }

    processed = process_asset_plan_elements(case_dir, plan, ["A001"], rmbg_client=FakeRmbgClient())

    element = processed["asset_plan"]["elements"][0]
    assert element["processing_status"] == "processed"
    assert element["processed_asset_source_strategy"] == "crop_nobg"
    result_path = case_dir / element["processed_asset_relative_path"]
    assert result_path.exists()
    with Image.open(result_path) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0
    assert processed["processed_assets"][0]["rmbg_elapsed_ms"] == 4.0


def test_materialize_approved_assets_uses_processed_nobg_result(tmp_path: Path) -> None:
    case_dir = tmp_path / "case"
    (case_dir / "inputs").mkdir(parents=True)
    source = Image.new("RGBA", (12, 12), (255, 255, 255, 255))
    for x in range(3, 9):
        for y in range(3, 9):
            source.putpixel((x, y), (20, 120, 220, 255))
    source.save(case_dir / "inputs" / "figure.png")
    plan = {
        "schema": "drawai.workbench_asset_plan.v1",
        "case_id": "case_1",
        "elements": [
            {
                "box_id": "A001",
                "bbox": [2, 2, 10, 10],
                "source_strategy": "crop_nobg",
                "type": "image",
            }
        ],
    }
    processed = process_asset_plan_elements(case_dir, plan, ["A001"], rmbg_client=FakeRmbgClient())
    write_asset_draft(case_dir, processed["asset_plan"])
    approve_asset_plan(case_dir)

    manifest = materialize_approved_assets(case_dir)

    asset = manifest["assets"][0]
    assert asset["active_variant"] == "without_background"
    assert asset["svg_href"] == "../svg_to_ppt/assets/crops/run0_refined/R0_A001_nobg.png"
    nobg_path = case_dir / "svg_to_ppt" / "assets" / "crops" / "run0_refined" / "R0_A001_nobg.png"
    with Image.open(nobg_path) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0))[3] == 0


class FakeRmbgClient:
    def remove_background(self, image: Image.Image, output_name: str, **_: object) -> RmbgResult:
        result = image.convert("RGBA")
        pixels = result.load()
        assert pixels is not None
        for x in range(result.width):
            for y in range(result.height):
                r, g, b, a = result.getpixel((x, y))
                if r > 240 and g > 240 and b > 240:
                    result.putpixel((x, y), (255, 255, 255, 0))
                else:
                    result.putpixel((x, y), (r, g, b, a))
        return RmbgResult(image=result, artifacts={"runtime": "fake"}, elapsed_ms=4.0)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
