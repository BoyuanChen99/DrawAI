from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from drawai.page_spec import fuse_page_specs, validate_page_spec_payload, write_page_spec
from drawai.page_spec_assets import materialize_page_spec_assets, materialized_asset_records
from drawai.page_spec_svg import draft_semantic_svg_from_page_spec
from drawai.tooling import drawai_tool_cli


def test_fuse_page_specs_outputs_page_spec_elements_without_legacy_payloads() -> None:
    fused = fuse_page_specs(
        (
            _page_spec(
                "sam",
                [
                    {
                        "id": "S001",
                        "kind": "image",
                        "role": "picture",
                        "box_px": [2, 3, 10, 12],
                        "z_index": 5,
                        "confidence": 0.92,
                        "build": {"mode": "asset_ref", "processing_type": "crop"},
                        "source_refs": [{"kind": "candidate", "id": "sam:B001"}],
                    }
                ],
            ),
            _page_spec(
                "ocr",
                [
                    {
                        "id": "T001",
                        "kind": "text",
                        "role": "text",
                        "box_px": [4, 5, 8, 3],
                        "z_index": 6,
                        "text": "Hello",
                        "build": {"mode": "editable_text", "processing_type": "svg_self_draw"},
                        "source_refs": [{"kind": "candidate", "id": "ocr:T001"}],
                    }
                ],
            ),
        ),
        page_id="page-1",
        source_image="inputs/source.png",
    )

    validate_page_spec_payload(fused)
    assert [element["id"] for element in fused["elements"]] == ["E001", "E002"]
    assert fused["elements"][0]["build"]["processing_type"] == "crop"
    assert "candidate_payload" not in fused["elements"][0]["metadata"]
    assert fused["metadata"] == {}


def test_materialize_page_spec_assets_writes_bundle_relative_paths(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (24, 24), (255, 255, 255, 255)).save(source)
    output_dir = tmp_path / "node" / "output"
    page_spec = _page_spec(
        "refine",
        [
            {
                "id": "E001",
                "kind": "image",
                "role": "picture",
                "box_px": [2, 3, 10, 12],
                "z_index": 5,
                "build": {"mode": "asset_ref", "processing_type": "crop"},
                "source_refs": [{"kind": "page_spec_element", "id": "S001"}],
            },
            {
                "id": "E002",
                "kind": "text",
                "role": "text",
                "box_px": [1, 1, 4, 4],
                "build": {"mode": "editable_text", "processing_type": "svg_self_draw"},
            },
        ],
    )

    materialized = materialize_page_spec_assets(page_spec, source_image_path=source, output_dir=output_dir)
    page_spec_path = write_page_spec(output_dir / "page_spec.json", materialized)

    element = materialized["elements"][0]
    assert element["materialization"]["outputs"]["active"]["path"] == "assets/E001/active.png"
    assert (output_dir / "assets" / "E001" / "active.png").is_file()
    assert "materialization" not in materialized["elements"][1]
    records = materialized_asset_records(page_spec_path, svg_dir=tmp_path / "svg")
    assert records[0]["element_id"] == "E001"
    assert records[0]["svg_href"].endswith("node/output/assets/E001/crop.png")


def test_draft_semantic_svg_from_materialized_page_spec_uses_active_asset_href(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    Image.new("RGBA", (48, 32), (255, 255, 255, 255)).save(source)
    output_dir = tmp_path / "node" / "output"
    page_spec = _page_spec(
        "refine",
        [
            {
                "id": "E001",
                "kind": "image",
                "role": "picture",
                "box_px": [2, 3, 16, 12],
                "z_index": 5,
                "build": {"mode": "asset_ref", "processing_type": "crop"},
            },
            {
                "id": "E002",
                "kind": "text",
                "role": "text",
                "box_px": [20, 8, 18, 8],
                "z_index": 6,
                "text": "Hello",
                "build": {"mode": "editable_text", "processing_type": "svg_self_draw"},
            },
        ],
    )
    materialized = materialize_page_spec_assets(page_spec, source_image_path=source, output_dir=output_dir)
    page_spec_path = write_page_spec(output_dir / "page_spec.json", materialized)
    svg_path = tmp_path / "nodes" / "svg_compose" / "runs" / "001" / "output" / "semantic.svg"

    result = draft_semantic_svg_from_page_spec(page_spec_path, svg_path, href_base_dir=tmp_path / "svg")

    svg = svg_path.read_text(encoding="utf-8")
    assert result["asset_images"] == 1
    assert 'href="../node/output/assets/E001/active.png"' in svg
    assert 'data-pb-editable="false"' in svg
    assert ">Hello</text>" in svg


def test_page_spec_svg_draft_tool_promotes_validated_draft_outputs(tmp_path: Path, capsys) -> None:  # type: ignore[no-untyped-def]
    source = tmp_path / "source.png"
    Image.new("RGBA", (48, 32), (255, 255, 255, 255)).save(source)
    output_dir = tmp_path / "node" / "output"
    page_spec = _page_spec(
        "refine",
        [
            {
                "id": "E001",
                "kind": "image",
                "role": "picture",
                "box_px": [2, 3, 16, 12],
                "z_index": 5,
                "build": {"mode": "asset_ref", "processing_type": "crop"},
            },
            {
                "id": "E002",
                "kind": "text",
                "role": "text",
                "box_px": [20, 8, 18, 8],
                "z_index": 6,
                "text": "Hello",
                "build": {"mode": "editable_text", "processing_type": "svg_self_draw"},
            },
        ],
    )
    materialized = materialize_page_spec_assets(page_spec, source_image_path=source, output_dir=output_dir)
    page_spec_path = write_page_spec(output_dir / "page_spec.json", materialized)
    svg_output_dir = tmp_path / "nodes" / "svg_compose" / "runs" / "001" / "output"

    exit_code = drawai_tool_cli(
        [
            "page-spec-svg-draft",
            "--page-spec",
            str(page_spec_path),
            "--svg",
            str(svg_output_dir / "semantic_0.svg"),
            "--href-base-dir",
            str(tmp_path / "svg"),
            "--rendered",
            str(svg_output_dir / "rendered_0.png"),
            "--report",
            str(svg_output_dir / "validation_report_0.json"),
            "--iteration-log-md",
            str(svg_output_dir / "iteration_log.md"),
            "--iteration-log-jsonl",
            str(svg_output_dir / "iteration_log.jsonl"),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["validation"]["status"] == "ok"
    assert payload["finalized_outputs"]["semantic_svg"] == str(svg_output_dir / "semantic.svg")
    assert (svg_output_dir / "semantic.svg").read_text(encoding="utf-8") == (
        svg_output_dir / "semantic_0.svg"
    ).read_text(encoding="utf-8")
    assert (svg_output_dir / "semantic_svg.svg").read_text(encoding="utf-8") == (
        svg_output_dir / "semantic_0.svg"
    ).read_text(encoding="utf-8")
    assert (svg_output_dir / "rendered.png").is_file()
    assert (svg_output_dir / "validation_report_final.json").is_file()


def _page_spec(source: str, elements: list[dict[str, object]]) -> dict[str, object]:
    return {
        "schema": "drawai.page_spec.v1",
        "page_id": "page-1",
        "source": {"image": "inputs/source.png", "width_px": 24, "height_px": 24},
        "canvas": {"width_px": 24, "height_px": 24},
        "background": {},
        "elements": elements,
        "metadata": {"source": source},
    }
