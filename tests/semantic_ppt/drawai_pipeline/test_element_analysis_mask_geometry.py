from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from PIL import Image, ImageDraw

from drawai.workbench.assets import validate_asset_plan


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_codex_element_analysis.py"


def _load_run0_module():
    spec = importlib.util.spec_from_file_location("run_codex_element_analysis", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def test_run0_request_uses_mask_preview_and_enrichment_restores_mask_geometry(tmp_path: Path):
    module = _load_run0_module()
    case_dir = tmp_path / "case"
    figure_path = case_dir / "inputs" / "figure.png"
    figure_path.parent.mkdir(parents=True)
    Image.new("RGBA", (20, 20), (180, 210, 245, 255)).save(figure_path)

    mask_path = case_dir / "sam3" / "masks" / "B001.png"
    mask_path.parent.mkdir(parents=True)
    mask = Image.new("L", (20, 20), 0)
    ImageDraw.Draw(mask).ellipse([4, 4, 15, 15], fill=255)
    mask.save(mask_path)

    _write_json(
        case_dir / "box_ir" / "box_ir.json",
        {
            "boxes": [
                {
                    "id": "B001",
                    "type": "icon",
                    "bbox": [4, 4, 16, 16],
                    "geometry": {
                        "kind": "mask",
                        "mask_path": "sam3/masks/B001.png",
                        "bbox": [4, 4, 16, 16],
                    },
                }
            ]
        },
    )

    output_dir = case_dir / "reports" / "element_analysis_codex"
    request = module.build_request(case_dir, output_dir)
    candidate = request["candidates"][0]
    assert candidate["geometry_kind"] == "mask"
    assert candidate["geometry_locked"] is True
    assert candidate["geometry"]["kind"] == "mask"
    assert "mask_path" not in candidate["geometry"]
    preview_path = case_dir / candidate["geometry_preview"]
    assert preview_path.is_file()
    assert (case_dir / request["mask_preview_sheet"]).is_file()
    with Image.open(preview_path) as preview:
        assert preview.convert("RGBA").getpixel((0, 0))[3] == 0

    module.write_json(output_dir / "element_analysis_request.json", request)
    analysis = {
        "schema": module.SCHEMA_OUTPUT,
        "elements": [
            {
                "box_id": "B001",
                "source_candidate_ids": ["B001"],
                "refinement_action": "adjusted",
                "category": "crop",
                "confidence": "high",
                "visual_role": "masked icon",
                "reason": "Kept as source crop.",
                "bbox": [0, 0, 3, 3],
                "type": "icon",
            }
        ],
    }
    enriched = module.enrich_analysis_with_source_geometry(case_dir, analysis)
    element = enriched["elements"][0]
    assert element["bbox"] == [4.0, 4.0, 16.0, 16.0]
    assert element["geometry"]["kind"] == "mask"
    assert element["geometry"]["mask_path"] == "sam3/masks/B001.png"
    assert element["geometry_locked"] is True
    assert element["geometry_preview_relative_path"] == candidate["geometry_preview"]

    validated = validate_asset_plan({"elements": enriched["elements"]})
    draft_element = validated["elements"][0]
    assert draft_element["geometry"]["kind"] == "mask"
    assert draft_element["geometry_preview_relative_path"] == candidate["geometry_preview"]
    assert draft_element["geometry_locked"] is True
