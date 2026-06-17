import json
from pathlib import Path

import pytest
from PIL import Image

from drawai.public_stages import PUBLIC_STAGE_ORDER, run_public_stage


def test_public_stage_order_exposes_coarse_pipeline_boundaries():
    assert PUBLIC_STAGE_ORDER == (
        "prepare",
        "detect_structure",
        "detect_text",
        "assemble_boxir",
        "asset_plan",
        "asset_analyze",
        "asset_materialize",
        "svg",
        "export",
    )


def _write_minimal_public_config(tmp_path: Path) -> Path:
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
    enabled: true
svg_to_ppt:
  enabled: true
  export_pptx: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text('{"ocr_text_boxes":[]}', encoding="utf-8")
    return config


def _stub_public_frontend_stages(monkeypatch) -> None:
    monkeypatch.setattr("drawai.public_stages._run_prepare", lambda cfg, paths: None)
    monkeypatch.setattr("drawai.public_stages._run_detect_structure", lambda cfg, paths, *, sam3_transport: None)
    monkeypatch.setattr("drawai.public_stages._run_detect_text", lambda cfg, paths, *, ocr_provider: None)
    monkeypatch.setattr("drawai.public_stages._run_assemble_boxir", lambda cfg, paths, *, sources: None)


@pytest.mark.parametrize(
    ("stage", "expected_low_level_stage", "expected_to_stage", "expect_rmbg_client"),
    [
        ("asset_analyze", "codex_run0_asset_analysis_completed", "codex_run0_asset_analysis_completed", False),
        ("asset_materialize", "assets_materialized", "assets_materialized", True),
        ("svg", "assets_materialized", "svg_generated", True),
    ],
)
def test_public_asset_stages_materialize_only_after_analysis(
    monkeypatch,
    tmp_path: Path,
    stage: str,
    expected_low_level_stage: str,
    expected_to_stage: str | None,
    expect_rmbg_client: bool,
):
    config = _write_minimal_public_config(tmp_path)
    sentinel_rmbg_client = object()
    calls: list[dict[str, object]] = []

    def fake_run_drawai_pipeline_from_stage(cfg, low_level_stage, **kwargs):
        calls.append(
            {
                "low_level_stage": low_level_stage,
                "to_stage": kwargs.get("to_stage"),
                "rmbg_client": kwargs.get("rmbg_client"),
            }
        )
        return {"status": "ok", "stages": [low_level_stage], "artifacts": {}}

    monkeypatch.setattr("drawai.public_stages.run_drawai_pipeline_from_stage", fake_run_drawai_pipeline_from_stage)

    summary = run_public_stage(config, stage, rmbg_client=sentinel_rmbg_client)

    assert summary["status"] == "ok"
    assert calls == [
        {
            "low_level_stage": expected_low_level_stage,
            "to_stage": expected_to_stage,
            "rmbg_client": sentinel_rmbg_client if expect_rmbg_client else None,
        }
    ]


def test_public_all_passes_rmbg_client_only_to_materialize(monkeypatch, tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)
    sentinel_rmbg_client = object()
    calls: list[dict[str, object]] = []

    def fake_run_drawai_pipeline_from_stage(cfg, low_level_stage, **kwargs):
        calls.append(
            {
                "low_level_stage": low_level_stage,
                "to_stage": kwargs.get("to_stage"),
                "rmbg_client": kwargs.get("rmbg_client"),
            }
        )
        return {"status": "ok", "stages": [low_level_stage], "artifacts": {}}

    _stub_public_frontend_stages(monkeypatch)
    monkeypatch.setattr("drawai.public_stages.run_drawai_pipeline_from_stage", fake_run_drawai_pipeline_from_stage)

    summary = run_public_stage(config, "all", rmbg_client=sentinel_rmbg_client, parallel=False)

    assert summary["status"] == "ok"
    assert [
        call for call in calls if call["low_level_stage"] == "assets_materialized"
    ][0]["rmbg_client"] is sentinel_rmbg_client
    assert [
        call for call in calls if call["low_level_stage"] == "codex_run0_asset_analysis_completed"
    ][0]["rmbg_client"] is None
    assert [call["low_level_stage"] for call in calls] == [
        "asset_decisions_completed",
        "codex_run0_asset_analysis_completed",
        "assets_materialized",
        "svg_generated",
        "svg_to_ppt_exported",
    ]


def test_detect_text_and_assemble_text_only_from_prepare_output(tmp_path: Path):
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
svg_to_ppt:
  enabled: true
  export_pptx: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text(
        '{"ocr_text_boxes":[{"id":"T001","bbox":[4,5,20,14],"text":"Hello","confidence":0.9}]}',
        encoding="utf-8",
    )

    prepare_summary = run_public_stage(config, "prepare")
    text_summary = run_public_stage(config, "detect_text")
    assemble_summary = run_public_stage(config, "assemble_boxir", sources="text")

    assert prepare_summary["public_stage"] == "prepare"
    assert text_summary["public_stage"] == "detect_text"
    assert assemble_summary["public_stage"] == "assemble_boxir"
    assert assemble_summary["sources"] == "text"
    box_ir = json.loads(Path(assemble_summary["artifacts"]["box_ir"]).read_text(encoding="utf-8"))
    assert box_ir["boxes"] == []
    assert [item["text"] for item in box_ir["ocr_text_boxes"]] == ["Hello"]


def test_detect_structure_and_assemble_structure_only_from_prepare_output(tmp_path: Path):
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
svg_to_ppt:
  enabled: true
  export_pptx: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text('{"ocr_text_boxes":[]}', encoding="utf-8")

    class FakeSam3Transport:
        def post_json(self, path, payload, timeout_s):
            return {
                "regions": [{"bbox": [10, 10, 30, 25], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    prepare_summary = run_public_stage(config, "prepare")
    structure_summary = run_public_stage(config, "detect_structure", sam3_transport=FakeSam3Transport())
    assemble_summary = run_public_stage(config, "assemble_boxir", sources="structure")

    assert prepare_summary["public_stage"] == "prepare"
    assert structure_summary["public_stage"] == "detect_structure"
    assert assemble_summary["sources"] == "structure"
    box_ir = json.loads(Path(assemble_summary["artifacts"]["box_ir"]).read_text(encoding="utf-8"))
    assert len(box_ir["boxes"]) == 1
    assert box_ir["ocr_text_boxes"] == []


def test_public_all_stops_when_low_level_svg_stage_fails(monkeypatch, tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)
    _stub_public_frontend_stages(monkeypatch)

    def fake_run_drawai_pipeline_from_stage(cfg, low_level_stage, **kwargs):
        if low_level_stage == "svg_generated":
            return {
                "status": "failed",
                "failed_stage": "svg_generated",
                "stages": ["svg_generated"],
                "artifacts": {},
            }
        return {"status": "ok", "stages": [low_level_stage], "artifacts": {}}

    monkeypatch.setattr("drawai.public_stages.run_drawai_pipeline_from_stage", fake_run_drawai_pipeline_from_stage)

    summary = run_public_stage(
        config,
        "all",
        parallel=False,
    )

    assert summary["status"] == "failed"
    assert summary["failed_stage"] == "svg_generated"
    assert summary["public_stage"] == "svg"

    persisted = json.loads((tmp_path / "out" / "reports" / "pipeline_summary.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "failed"
    assert persisted["failed_stage"] == "svg_generated"
    assert persisted["public_stage"] == "svg"


def test_public_all_summary_records_internal_stage_chain(monkeypatch, tmp_path: Path):
    config = _write_minimal_public_config(tmp_path)
    _stub_public_frontend_stages(monkeypatch)

    def fake_run_drawai_pipeline_from_stage(cfg, low_level_stage, **_kwargs):
        return {"status": "ok", "stages": [low_level_stage], "artifacts": {}}

    monkeypatch.setattr("drawai.public_stages.run_drawai_pipeline_from_stage", fake_run_drawai_pipeline_from_stage)

    summary = run_public_stage(
        config,
        "all",
        parallel=False,
    )

    expected_stages = [
        "config_loaded",
        "input_normalized",
        "sam3_completed",
        "box_ir_merged",
        "semantic_overlay_rendered",
        "ocr_completed",
        "asset_decisions_completed",
        "codex_run0_asset_analysis_completed",
        "assets_materialized",
        "svg_generated",
        "svg_to_ppt_exported",
        "completed",
    ]
    assert summary["status"] == "ok"
    assert summary["stages"] == expected_stages
    assert summary["public_stages"] == list(PUBLIC_STAGE_ORDER)

    persisted = json.loads((tmp_path / "out" / "reports" / "pipeline_summary.json").read_text(encoding="utf-8"))
    assert persisted["stages"] == expected_stages
    assert persisted["public_stages"] == list(PUBLIC_STAGE_ORDER)
