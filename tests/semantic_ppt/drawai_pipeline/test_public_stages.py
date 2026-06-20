import json
from pathlib import Path

from PIL import Image

from drawai.public_stages import PUBLIC_STAGE_ORDER, run_public_stage


def test_public_stage_order_exposes_v2_pipeline_boundaries():
    assert PUBLIC_STAGE_ORDER == (
        "prepare",
        "parse_elements",
        "fuse_elements",
        "refine_elements",
        "plan_assets",
        "process_assets",
        "compose_svg",
        "export",
        "package_run",
    )


def test_legacy_detect_text_alias_still_runs_parser_stage(tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)

    summary = run_public_stage(config, "detect_text")

    assert summary["status"] == "ok"
    assert summary["public_stage"] == "parse_elements"
    assert summary["stage_alias"] == "detect_text"
    assert Path(summary["artifacts"]["v2_parser_outputs"]).is_dir()


def test_legacy_assemble_boxir_alias_writes_v2_derived_boxir(tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)

    summary = run_public_stage(config, "assemble_boxir")

    assert summary["status"] == "ok"
    assert summary["public_stage"] == "fuse_elements"
    assert summary["stage_alias"] == "assemble_boxir"
    box_ir = json.loads(Path(summary["artifacts"]["box_ir"]).read_text(encoding="utf-8"))
    assert box_ir["boxes"] == []
    assert [item["text"] for item in box_ir["ocr_text_boxes"]] == ["Hello"]


def test_legacy_structure_alias_can_use_injected_sam_transport(tmp_path: Path):
    config = _write_minimal_public_config(tmp_path, ocr_text_boxes="[]")

    class FakeSam3Transport:
        def post_json(self, path, payload, timeout_s):
            return {
                "regions": [{"bbox": [10, 10, 30, 25], "score": 0.9, "label": "icon"}],
                "raw_regions": [
                    {
                        "bbox": [10, 10, 30, 25],
                        "score": 0.9,
                        "label": "icon",
                    }
                ],
            }, 1.0

    summary = run_public_stage(
        config,
        "assemble_boxir",
        sam3_transport=FakeSam3Transport(),
    )

    assert summary["status"] == "ok"
    assert summary["public_stage"] == "fuse_elements"
    box_ir = json.loads(Path(summary["artifacts"]["box_ir"]).read_text(encoding="utf-8"))
    assert len(box_ir["boxes"]) == 1
    assert box_ir["ocr_text_boxes"] == []


def test_public_all_summary_records_v2_stage_chain(tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80 40" width="80" height="40"><rect width="80" height="40" fill="white"/><circle cx="20" cy="20" r="8" fill="#222"/></svg>'

    summary = run_public_stage(config, "all", parallel=False, svg_invoker=svg_invoker)

    assert summary["status"] == "ok"
    assert summary["public_stage"] == "all"
    assert summary["stages"] == list(PUBLIC_STAGE_ORDER)
    assert summary["public_stages"] == list(PUBLIC_STAGE_ORDER)
    assert Path(summary["artifacts"]["run_package"]).is_file()

    persisted = json.loads((tmp_path / "out" / "reports" / "pipeline_summary.json").read_text(encoding="utf-8"))
    assert persisted["stages"] == list(PUBLIC_STAGE_ORDER)
    assert persisted["public_stages"] == list(PUBLIC_STAGE_ORDER)


def _write_minimal_public_config(
    tmp_path: Path,
    *,
    ocr_text_boxes: str = '[{"id":"T001","bbox":[4,5,20,14],"text":"Hello","confidence":0.9}]',
) -> Path:
    image = tmp_path / "input.png"
    Image.new("RGB", (80, 40), "white").save(image)
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {image.name}
  output_dir: out
  normalization:
    enabled: false
sam3:
  prompts:
    - id: icon
      text: icon
      confidence_threshold: 0.3
ocr:
  provider: fixture
  fixture:
    path: ocr_fixture.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: true
  export_pptx: false
v2:
  refine:
    enabled: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text(
        f'{{"ocr_text_boxes":{ocr_text_boxes}}}',
        encoding="utf-8",
    )
    return config
