import argparse
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from drawai.artifacts import prepare_artifact_paths
from drawai.pipeline import (
    _box_merge_diagnostics,
    _svg_to_ppt_validation_asset_manifest,
    run_drawai_pipeline,
    run_drawai_pipeline_from_stage,
)
from drawai.rmbg_client import RmbgResult
from drawai.svg_generation_loop import SvgGenerationError


def _iter_manifest_paths(value):
    if isinstance(value, str):
        yield Path(value)
        return
    if isinstance(value, list):
        for item in value:
            yield from _iter_manifest_paths(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _iter_manifest_paths(item)


def test_pipeline_dry_run_with_fakes_writes_summary(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 2
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="80" cy="40" r="8" fill="red"/></svg>'

    class FakeRmbgClient:
        def remove_background(self, crop, output_name, *, timeout_s, model_path, artifact_prefix):
            rgba = crop.convert("RGBA")
            rgba.putalpha(180)
            return RmbgResult(image=rgba, artifacts={}, elapsed_ms=2.0)

    summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        rmbg_client=FakeRmbgClient(),
        svg_invoker=svg_invoker,
    )

    assert summary["status"] == "ok"
    assert summary["stages"] == [
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
    assert Path(summary["artifacts"]["box_ir"]).exists()
    assert Path(summary["artifacts"]["box_ir_merged"]).exists()
    assert Path(summary["artifacts"]["semantic_svg"]).exists()
    assert Path(summary["artifacts"]["pipeline_summary"]).exists()
    assert Path(summary["artifacts"]["stage_io_manifest"]).exists()
    assert Path(summary["artifacts"]["svg_to_ppt_export_report"]).exists()
    assert Path(summary["artifacts"]["sam_boxes_by_prompt"]).exists()
    assert Path(summary["artifacts"]["box_merge_diagnostics"]).exists()
    assert Path(summary["artifacts"]["semantic_overlay_legend_image"]).exists()
    assert Path(summary["artifacts"]["final_semantic_overlay"]).exists()
    assert Path(summary["artifacts"]["final_semantic_overlay_legend_image"]).exists()
    assert Path(summary["artifacts"]["initial_asset_decisions"]).exists()
    assert Path(summary["artifacts"]["svg_recoverable_assets"]).exists()
    assert summary["artifacts"]["asset_recovery_reference"] != summary["artifacts"]["visual_template_reference"]
    assert Path(summary["artifacts"]["asset_recovery_reference"]).exists()
    assert Path(summary["artifacts"]["svg_generation_reference"]).exists()
    assert Path(summary["artifacts"]["visual_template_reference"]).exists()
    assert Path(summary["artifacts"]["svg_template_ir"]).exists()
    assert Path(summary["artifacts"]["template_iterations"]).exists()
    assert Path(summary["artifacts"]["template_svg"]).exists()

    stage_io_manifest = json.loads(Path(summary["artifacts"]["stage_io_manifest"]).read_text(encoding="utf-8"))
    assert stage_io_manifest["schema"] == "drawai.stage_io_manifest.v1"
    assert stage_io_manifest["execution_mode"] == "full_pipeline"
    stage_io = stage_io_manifest["stages"]
    assert list(stage_io) == [
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
    ]
    assert stage_io["box_ir_merged"]["outputs"]["merged_box_ir"] == summary["artifacts"]["box_ir_merged"]
    assert stage_io["ocr_completed"]["inputs"]["merged_box_ir"] == summary["artifacts"]["box_ir_merged"]
    assert stage_io["ocr_completed"]["outputs"]["final_box_ir"] == summary["artifacts"]["box_ir"]
    assert stage_io["codex_run0_asset_analysis_completed"]["outputs"]["element_analysis"] == summary["artifacts"]["element_analysis"]
    assert "asset_manifest" not in stage_io["codex_run0_asset_analysis_completed"]["outputs"]
    assert stage_io["assets_materialized"]["inputs"]["element_analysis"] == summary["artifacts"]["element_analysis"]
    assert stage_io["assets_materialized"]["outputs"]["asset_manifest"] == summary["artifacts"]["asset_manifest"]
    assert stage_io["svg_generated"]["inputs"]["box_ir"] == summary["artifacts"]["box_ir"]
    assert stage_io["svg_generated"]["inputs"]["asset_manifest"] == summary["artifacts"]["asset_manifest"]
    assert stage_io["svg_generated"]["inputs"]["svg_template_ir"] == summary["artifacts"]["svg_template_ir"]
    assert stage_io["svg_generated"]["inference_slots"] == ["svg_invoker", "model_runtime"]
    assert stage_io["svg_to_ppt_exported"]["inputs"]["semantic_svg"] == summary["artifacts"]["semantic_svg"]
    assert stage_io["svg_to_ppt_exported"]["inputs"]["asset_manifest"] == summary["artifacts"]["asset_manifest"]

    for stage_payload in stage_io.values():
        for artifact_path in _iter_manifest_paths(stage_payload["outputs"]):
            assert artifact_path.exists(), artifact_path

    box_ir = json.loads(Path(summary["artifacts"]["box_ir"]).read_text(encoding="utf-8"))
    assert box_ir["ocr_text_boxes"] == []
    template_ir = json.loads(Path(summary["artifacts"]["svg_template_ir"]).read_text(encoding="utf-8"))
    assert template_ir["schema"] == "drawai.box_ir.svg_template_ir.v1"
    assert Path(summary["artifacts"]["box_ir_raw"]).exists()
    sam_boxes = json.loads(Path(summary["artifacts"]["sam_boxes_by_prompt"]).read_text(encoding="utf-8"))
    assert sam_boxes["prompts"][0]["prompt_id"] == "icon"
    assert sam_boxes["prompts"][0]["box_count"] == 1
    merge_diagnostics = json.loads(Path(summary["artifacts"]["box_merge_diagnostics"]).read_text(encoding="utf-8"))
    assert merge_diagnostics["raw_box_count"] == 1
    assert merge_diagnostics["merged_box_count"] == 1
    manifest = json.loads(Path(summary["artifacts"]["asset_manifest"]).read_text(encoding="utf-8"))
    assert manifest["assets"] == []
    svg_recoverable = json.loads(Path(summary["artifacts"]["svg_recoverable_assets"]).read_text(encoding="utf-8"))
    assert svg_recoverable["source"] == "asset_policy"
    assert svg_recoverable["recoverable_asset_ids"] == ["AF01"]
    svg_generation_reference = Image.open(summary["artifacts"]["svg_generation_reference"]).convert("RGB")
    masked_icon_crop = svg_generation_reference.crop((12, 12, 38, 28))
    masked_gray_pixels = sum(
        count
        for count, color in masked_icon_crop.getcolors(maxcolors=10_000)
        if color == (128, 128, 128)
    )
    assert masked_gray_pixels == 0


def test_pipeline_can_rerun_svg_stage_from_persisted_stage_inputs(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 1
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def first_svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="50" cy="25" r="8" fill="#1f5fbf"/></svg>'

    full_summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=first_svg_invoker,
    )
    assert full_summary["status"] == "ok"

    Path(full_summary["artifacts"]["semantic_svg"]).unlink()

    def second_svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="50" cy="25" r="8" fill="#00aa00"/></svg>'

    rerun_summary = run_drawai_pipeline_from_stage(
        config,
        "svg_generated",
        to_stage="svg_to_ppt_exported",
        svg_invoker=second_svg_invoker,
    )

    assert rerun_summary["status"] == "ok"
    assert rerun_summary["execution_mode"] == "file_stage_runner"
    assert rerun_summary["from_stage"] == "svg_generated"
    assert rerun_summary["to_stage"] == "svg_to_ppt_exported"
    assert rerun_summary["stages"] == ["svg_generated", "svg_to_ppt_exported"]
    semantic_svg = Path(rerun_summary["artifacts"]["semantic_svg"]).read_text(encoding="utf-8")
    assert "#00aa00" in semantic_svg
    stage_io_manifest = json.loads(Path(rerun_summary["artifacts"]["stage_io_manifest"]).read_text(encoding="utf-8"))
    assert stage_io_manifest["stages"]["svg_generated"]["execution_mode"] == "file_stage_runner"


def test_export_stage_promotes_legacy_svg_to_ooxml_asset_manifest(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
  export_pptx: true
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text('{"ocr_text_boxes":[]}', encoding="utf-8")
    paths = prepare_artifact_paths(tmp_path / "out")
    legacy_asset = paths.root / "svg_to_ooxml" / "assets" / "crops" / "run0_refined" / "R0_B005.png"
    legacy_asset.parent.mkdir(parents=True)
    legacy_asset.write_bytes(b"png")
    paths.semantic_svg.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50">
  <image href="../svg_to_ooxml/assets/crops/run0_refined/R0_B005.png" x="0" y="0" width="10" height="10"/>
</svg>""",
        encoding="utf-8",
    )
    legacy_manifest = paths.root / "svg_to_ooxml" / "assets" / "asset_manifest.json"
    legacy_manifest.write_text(
        json.dumps(
            {
                "schema": "drawai.asset_manifest.v1",
                "assets": [
                    {
                        "asset_id": "R0_B005",
                        "bbox": [0, 0, 10, 10],
                        "svg_href": "../svg_to_ooxml/assets/crops/run0_refined/R0_B005.png",
                        "width": 10,
                        "height": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    assert not paths.asset_manifest_json.exists()

    def fake_compiler(svg_path, output_pptx):
        assert svg_path == paths.semantic_svg
        assert paths.asset_manifest_json.exists()
        output_pptx.parent.mkdir(parents=True, exist_ok=True)
        output_pptx.write_bytes(b"pptx")
        return {"backend": "fake"}

    summary = run_drawai_pipeline_from_stage(
        config,
        "svg_to_ppt_exported",
        to_stage="svg_to_ppt_exported",
        svg_to_ppt_compiler=fake_compiler,
    )

    assert summary["status"] == "ok"
    promoted_manifest = json.loads(paths.asset_manifest_json.read_text(encoding="utf-8"))
    assert promoted_manifest["assets"][0]["svg_href"] == "../svg_to_ooxml/assets/crops/run0_refined/R0_B005.png"
    assert (paths.root / "svg_to_ppt" / "semantic.svg_to_ppt.pptx").exists()


def test_svg_to_ppt_validation_manifest_includes_existing_native_backfill_assets(tmp_path: Path):
    paths = prepare_artifact_paths(tmp_path / "case")
    request_dir = paths.attempts_dir / "codex_merged" / "001"
    request_dir.mkdir(parents=True)
    native_asset_dir = paths.svg_dir / "native_backfill_assets" / "codex_merged_001"
    native_asset_dir.mkdir(parents=True)
    Image.new("RGBA", (10, 8), (255, 0, 0, 180)).save(native_asset_dir / "AF04_nobg.png")
    (request_dir / "native_backfill_request.json").write_text(
        json.dumps(
            {
                "schema": "drawai.native_backfill_request.v1",
                "candidates": [
                    {
                        "asset_id": "AF04",
                        "box_id": "B004",
                        "bbox": [10, 12, 20, 20],
                        "preserve_href": "native_backfill_assets/codex_merged_001/AF04.png",
                        "nobg_href": "native_backfill_assets/codex_merged_001/AF04_nobg.png",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    base_manifest = {
        "schema": "drawai.asset_manifest.v1",
        "assets": [{"asset_id": "R0_B001", "svg_href": "../assets/crops/R0_B001.png"}],
    }

    validation_manifest, extension = _svg_to_ppt_validation_asset_manifest(paths, base_manifest)

    hrefs = {asset["svg_href"] for asset in validation_manifest["assets"]}
    assert "../assets/crops/R0_B001.png" in hrefs
    assert "native_backfill_assets/codex_merged_001/AF04_nobg.png" in hrefs
    assert "native_backfill_assets/codex_merged_001/AF04.png" not in hrefs
    assert extension["manifest_extended"] is True
    assert extension["native_backfill_asset_count"] == 1
    assert extension["native_backfill_request_count"] == 1


def test_template_reference_removes_recovered_icons_from_stage_one_placeholders(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 1
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="50" cy="25" r="8" fill="#1f5fbf"/></svg>'

    summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=svg_invoker,
    )

    asset_decisions = json.loads(Path(summary["artifacts"]["asset_decisions"]).read_text(encoding="utf-8"))
    assert asset_decisions["decisions"][0]["decision"] == "native_svg"
    assert asset_decisions["decisions"][0]["recovered_asset_id"] == "AF01"

    asset_recovery_reference = Image.open(summary["artifacts"]["asset_recovery_reference"]).convert("RGB")
    initial_icon_crop = asset_recovery_reference.crop((12, 12, 38, 28))
    initial_gray_pixels = sum(
        count
        for count, color in initial_icon_crop.getcolors(maxcolors=10_000)
        if color == (128, 128, 128)
    )
    assert initial_gray_pixels > 0

    reference = Image.open(summary["artifacts"]["visual_template_reference"]).convert("RGB")
    icon_crop = reference.crop((12, 12, 38, 28))
    assert icon_crop.getcolors(maxcolors=10_000)
    gray_pixels = sum(
        count
        for count, color in icon_crop.getcolors(maxcolors=10_000)
        if color == (128, 128, 128)
    )
    assert gray_pixels == 0

    assert not (tmp_path / "out" / "trace" / "asset_selection_summary.json").exists()


def test_pipeline_uses_asset_policy_for_svg_recoverable_assets(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
asset_policy:
  enabled: true
svg:
  max_attempts: 1
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="50" cy="25" r="8" fill="#1f5fbf"/></svg>'

    summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=svg_invoker,
    )

    assert summary["status"] == "ok"
    policy_report = json.loads(Path(summary["artifacts"]["asset_policy_report"]).read_text(encoding="utf-8"))
    assert policy_report["schema"] == "drawai.asset_policy_report.v1"
    assert policy_report["asset_count"] == 1
    svg_recoverable = json.loads(Path(summary["artifacts"]["svg_recoverable_assets"]).read_text(encoding="utf-8"))
    assert svg_recoverable["source"] == "asset_policy"
    assert not (tmp_path / "out" / "trace" / "asset_selection_summary.json").exists()


def test_box_merge_diagnostics_flags_high_overlap_different_type_pairs():
    boxes = [
        {"id": "B001", "type": "icon", "bbox": [10, 10, 60, 60], "source_box_ids": ["R001"]},
        {"id": "B002", "type": "symbol", "bbox": [10, 10, 60, 60], "source_box_ids": ["R002"]},
    ]

    diagnostics = _box_merge_diagnostics(
        raw_box_ir={"boxes": boxes},
        merged_box_ir={"boxes": boxes},
        merge_trace={"decisions": []},
    )

    assert diagnostics["status"] == "review"
    warning = diagnostics["warnings"][0]
    assert warning["code"] == "high_overlap_different_type_pairs"
    assert warning["count"] == 1
    assert warning["samples"][0]["left_id"] == "B001"
    assert warning["samples"][0]["right_id"] == "B002"


def test_cli_dry_run_config_prints_default_summary():
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "drawai.cli",
            "--config",
            "configs/drawai/config.yaml",
            "--dry-run-config",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["input"]["normalization"]["target_long_edge"] == 2048
    assert len(payload["sam3"]["prompts"]) == 6
    assert "symbol" not in {prompt["id"] for prompt in payload["sam3"]["prompts"]}
    assert payload["ocr"]["provider"] == "remote_paddleocr"
    assert payload["svg"]["text_rendering"] == "model_text"
    assert payload["svg"]["visual_review_rounds"] == ["text_style"]
    assert payload["asset_materialization"]["rmbg"]["enabled"] is True
    assert payload["asset_materialization"]["rmbg"]["provider"] == "service"
    assert payload["model_runtime"]["provider"] == "codex-python-sdk"
    assert payload["model_runtime"]["connection_id"] == "codex-python-sdk-controlled"
    assert payload["model_runtime"]["model_name"] == ""
    assert payload["model_runtime"]["reasoning_effort"] == "xhigh"
    assert payload["model_runtime"]["base_url"] == ""
    assert payload["model_runtime"]["timeout_seconds"] == 1500


def test_cli_setup_local_dry_run_prints_single_setup_flow(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    result = main(
        [
            "setup",
            "local",
            "--full",
            "--dry-run",
            "--runtime-root",
            str(runtime_root),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "download_drawai_local_models.sh" in captured.out
    assert "--source modelscope" in captured.out
    assert "--accept-sam3-license" not in captured.out
    assert "--accept-rmbg-license" in captured.out
    assert "bootstrap_drawai_local_runtime.sh" in captured.out
    assert "DRAWAI_TORCH_SPEC=torch>=2.4,<2.12" in captured.out
    assert "DRAWAI_TORCHVISION_SPEC=torchvision>=0.19,<0.27" in captured.out
    assert "DRAWAI_DEVICE=cpu" in captured.out
    assert "DRAWAI_TORCH_BACKEND=cpu" in captured.out
    assert "DRAWAI_TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu" in captured.out
    assert "dry_run: no files were downloaded or modified" in captured.out


def test_cli_setup_local_device_gpu_selects_detected_cuda_backend(tmp_path: Path, capsys, monkeypatch):
    from drawai import local_cli
    from drawai.cli import main

    monkeypatch.setattr(local_cli, "_detect_torch_backend", lambda: "cu126")
    runtime_root = tmp_path / "runtime"
    result = main(["setup", "local", "--dry-run", "--runtime-root", str(runtime_root), "--device", "gpu"])

    captured = capsys.readouterr()
    assert result == 0
    assert "DRAWAI_DEVICE=gpu" in captured.out
    assert "DRAWAI_TORCH_BACKEND=cu126" in captured.out
    assert "DRAWAI_TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126" in captured.out


def test_cli_setup_local_device_gpu_requires_detected_cuda_backend(tmp_path: Path, monkeypatch):
    from drawai import local_cli
    from drawai.cli import main

    monkeypatch.setattr(local_cli, "_detect_torch_backend", lambda: "cpu")
    with pytest.raises(ValueError, match="--device gpu requires a detected NVIDIA CUDA runtime"):
        main(["setup", "local", "--dry-run", "--runtime-root", str(tmp_path / "runtime"), "--device", "gpu"])


def test_cli_setup_local_torch_backend_selects_pytorch_index(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    result = main(
        [
            "setup",
            "local",
            "--dry-run",
            "--runtime-root",
            str(runtime_root),
            "--torch-backend",
            "cu126",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "DRAWAI_TORCH_BACKEND=cu126" in captured.out
    assert "DRAWAI_TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126" in captured.out


def test_cli_setup_local_allows_torch_install_overrides(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    result = main(
        [
            "setup",
            "local",
            "--dry-run",
            "--runtime-root",
            str(runtime_root),
            "--torch-spec",
            "torch>=2.7,<2.12",
            "--torchvision-spec",
            "torchvision>=0.22,<0.27",
            "--torch-index-url",
            "https://download.pytorch.org/whl/cu126",
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "DRAWAI_TORCH_BACKEND=cpu" in captured.out
    assert "DRAWAI_TORCH_SPEC=torch>=2.7,<2.12" in captured.out
    assert "DRAWAI_TORCHVISION_SPEC=torchvision>=0.22,<0.27" in captured.out
    assert "DRAWAI_TORCH_INDEX_URL=https://download.pytorch.org/whl/cu126" in captured.out


def test_cli_setup_local_can_skip_torch_install(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    result = main(["setup", "local", "--dry-run", "--runtime-root", str(runtime_root), "--skip-torch-install"])

    captured = capsys.readouterr()
    assert result == 0
    assert "DRAWAI_SKIP_TORCH_INSTALL=1" in captured.out


def test_cli_setup_local_rmbg_acceptance_is_default(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    result = main(["setup", "local", "--dry-run", "--runtime-root", str(runtime_root)])

    captured = capsys.readouterr()
    assert result == 0
    assert "--rmbg" in captured.out
    assert "--accept-rmbg-license" in captured.out


def test_cli_setup_local_allows_unchecking_rmbg_license(tmp_path: Path):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    with pytest.raises(ValueError, match="RMBG-2.0 is enabled by default"):
        main(["setup", "local", "--dry-run", "--runtime-root", str(runtime_root), "--no-accept-rmbg-license"])


def test_cli_exposes_server_model_command(capsys):
    from drawai.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["server", "model", "--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "Run local DrawAI SAM3, OCR, and RMBG HTTP services." in captured.out
    assert "sam3" in captured.out
    assert "--device" in captured.out


def test_server_model_device_profile_maps_to_model_devices():
    from drawai.local_services import _parse_args

    default_args = _parse_args([])
    assert default_args.sam3_device == "cpu"
    assert default_args.rmbg_device == "cpu"
    assert default_args.paddle_device == "cpu"

    gpu_args = _parse_args(["--device", "gpu"])
    assert gpu_args.sam3_device == "cuda"
    assert gpu_args.rmbg_device == "cuda"
    assert gpu_args.paddle_device == "cpu"

    mps_args = _parse_args(["--device", "mps"])
    assert mps_args.sam3_device == "cpu"
    assert mps_args.rmbg_device == "mps"
    assert mps_args.paddle_device == "cpu"

    override_args = _parse_args(["--device", "gpu", "--sam3-device", "cpu"])
    assert override_args.sam3_device == "cpu"
    assert override_args.rmbg_device == "cuda"


def test_cli_exposes_server_api_command(capsys):
    from drawai.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["server", "api", "--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "Run the DrawAI Workbench API and pipeline backend." in captured.out
    assert "--model-api" in captured.out
    assert "--ocr-timeout-seconds" in captured.out


def test_server_api_starts_only_missing_local_models():
    from drawai.server_cli import _models_to_start

    assert _models_to_start(
        argparse.Namespace(model_api="", sam3_api="", ocr_api="", rmbg_api="")
    ) == ("sam3", "ocr", "rmbg")
    assert _models_to_start(
        argparse.Namespace(
            model_api="",
            sam3_api="http://sam:18080",
            ocr_api="",
            rmbg_api="http://rmbg:18080",
        )
    ) == ("ocr",)
    assert _models_to_start(
        argparse.Namespace(
            model_api="",
            sam3_api="http://sam:18080",
            ocr_api="http://ocr:18080",
            rmbg_api="http://rmbg:18080",
        )
    ) == ()
    assert _models_to_start(
        argparse.Namespace(
            model_api="http://model:18080",
            sam3_api="",
            ocr_api="",
            rmbg_api="",
        )
    ) == ()


def test_cli_exposes_workbench_command(capsys):
    from drawai.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["workbench", "--help"])

    captured = capsys.readouterr()
    assert exc.value.code == 0
    assert "Run the DrawAI Workbench frontend or full local workbench stack." in captured.out
    assert "--api" in captured.out


def test_workbench_frontend_install_command_prefers_lockfile(tmp_path: Path):
    from drawai.server_cli import _workbench_frontend_install_command

    assert _workbench_frontend_install_command(tmp_path) == ["npm", "install"]
    (tmp_path / "package-lock.json").write_text("{}", encoding="utf-8")
    assert _workbench_frontend_install_command(tmp_path) == ["npm", "ci"]


def test_workbench_frontend_only_uses_shared_launcher(monkeypatch):
    from drawai.server_cli import _run_frontend_only

    calls = []

    def fake_call(command, *, cwd, env):
        calls.append((command, cwd, env))
        return 0

    monkeypatch.setattr(subprocess, "call", fake_call)

    assert _run_frontend_only(api_url="http://127.0.0.1:8890/", host="0.0.0.0", port=5174) == 0
    command, cwd, env = calls[0]
    assert command[0].endswith("scripts/run_drawai_workbench_frontend.sh")
    assert (cwd / "scripts" / "run_drawai_workbench_frontend.sh").exists()
    assert env["DRAWAI_WORKBENCH_API_URL"] == "http://127.0.0.1:8890"
    assert env["DRAWAI_WORKBENCH_HOST"] == "0.0.0.0"
    assert env["DRAWAI_WORKBENCH_FRONTEND_PORT"] == "5174"


def test_cli_setup_local_huggingface_requires_sam3_acceptance(tmp_path: Path):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    with pytest.raises(ValueError, match="SAM3 Hugging Face download requires --accept-sam3-license"):
        main(
            [
                "setup",
                "local",
                "--dry-run",
                "--source",
                "huggingface",
                "--runtime-root",
                str(runtime_root),
            ]
        )


def test_cli_setup_local_success_message_uses_uv_run(tmp_path: Path, monkeypatch, capsys):
    from drawai.cli import main

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    runtime_root = tmp_path / "runtime"

    result = main(["setup", "local", "--bootstrap-only", "--runtime-root", str(runtime_root)])

    captured = capsys.readouterr()
    assert result == 0
    assert "next: uv run drawai doctor local" in captured.out
    assert "next: drawai doctor local" not in captured.out


def test_cli_setup_local_runs_doctor_after_full_setup(tmp_path: Path, monkeypatch, capsys):
    from drawai.cli import main
    from drawai.local_cli import DoctorCheck

    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0)

    def fake_checks(*, runtime_root, repo_root):
        return [
            DoctorCheck("runtime root", "ok", str(runtime_root)),
            DoctorCheck("SAM3 checkpoint", "ok", str(runtime_root / "models" / "sam3" / "sam3.pt")),
            DoctorCheck("SVG browser renderer", "warn", "Chrome/Chromium was not found on PATH."),
        ]

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("drawai.local_cli.local_runtime_checks", fake_checks)
    runtime_root = tmp_path / "runtime"

    result = main(["setup", "local", "--runtime-root", str(runtime_root)])

    captured = capsys.readouterr()
    assert result == 0
    assert len(commands) == 2
    assert "post_setup: running uv run drawai doctor local" in captured.out
    assert "DrawAI local doctor" in captured.out
    assert "status: ok" in captured.out
    assert "next: uv run drawai run /path/to/image.png --local" in captured.out


def test_cli_setup_local_skip_doctor_keeps_manual_next_step(tmp_path: Path, monkeypatch, capsys):
    from drawai.cli import main

    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0)

    def fail_checks(**kwargs):
        raise AssertionError("local_runtime_checks should not run with --skip-doctor")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("drawai.local_cli.local_runtime_checks", fail_checks)
    runtime_root = tmp_path / "runtime"

    result = main(["setup", "local", "--skip-doctor", "--runtime-root", str(runtime_root)])

    captured = capsys.readouterr()
    assert result == 0
    assert "doctor: skipped (--skip-doctor)" in captured.out
    assert "next: uv run drawai doctor local" in captured.out


def test_cli_setup_local_accepts_manual_sam3_sources(tmp_path: Path, capsys):
    from drawai.cli import main

    runtime_root = tmp_path / "runtime"
    sam3_source = tmp_path / "facebookresearch-sam3"
    sam3_checkpoint = tmp_path / "sam3.pt"
    sam3_bpe = tmp_path / "bpe_simple_vocab_16e6.txt.gz"

    result = main(
        [
            "setup",
            "local",
            "--dry-run",
            "--runtime-root",
            str(runtime_root),
            "--sam3-source",
            str(sam3_source),
            "--sam3-checkpoint",
            str(sam3_checkpoint),
            "--sam3-bpe",
            str(sam3_bpe),
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "manual_sam3" in captured.out
    assert "--source modelscope" in captured.out
    assert "--rmbg" in captured.out
    assert "--sam3 " not in captured.out
    assert "bootstrap_drawai_local_runtime.sh" in captured.out


def test_cli_doctor_local_json_reports_missing_runtime(tmp_path: Path, capsys):
    from drawai.cli import main

    result = main(["doctor", "local", "--json", "--runtime-root", str(tmp_path / "runtime")])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert result == 1
    assert payload["status"] == "needs_setup"
    assert payload["runtime_root"] == str((tmp_path / "runtime").resolve(strict=False))
    assert any(item["name"] == "runtime Python" and item["status"] == "missing" for item in payload["checks"])
    assert all("Run: drawai " not in item.get("fix", "") for item in payload["checks"])
    assert any("uv run drawai setup local" in item.get("fix", "") for item in payload["checks"])


def test_cli_doctor_local_text_uses_uv_run_next_step(tmp_path: Path, capsys):
    from drawai.cli import main

    result = main(["doctor", "local", "--runtime-root", str(tmp_path / "runtime")])

    captured = capsys.readouterr()
    assert result == 1
    assert "Readiness map" in captured.out
    assert "Runtime base" in captured.out
    assert "Model assets" in captured.out
    assert "Action queue" in captured.out
    assert "[MISS] root" in captured.out
    assert "[missing] runtime root:" not in captured.out
    assert "next: uv run drawai setup local" in captured.out
    assert "next: uv run drawai setup local --accept-rmbg-license" not in captured.out
    assert "next: drawai setup local" not in captured.out


def test_cli_run_image_local_dry_run_uses_single_command(tmp_path: Path, capfd):
    from PIL import Image

    from drawai.cli import main

    image = tmp_path / "figure.png"
    Image.new("RGB", (8, 8), "white").save(image)
    base_config = tmp_path / "base.yaml"
    base_config.write_text(
        """
input:
  image: placeholder.png
  output_dir: placeholder_out
sam3:
  prompts:
    - id: icon
      text: icon
      confidence_threshold: 0.3
ocr:
  provider: fixture
  fixture:
    path: ocr.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: false
""",
        encoding="utf-8",
    )

    result = main(
        [
            "run",
            str(image),
            "--local",
            "--dry-run",
            "--base-config",
            str(base_config),
            "--run-root",
            str(tmp_path / "runs"),
            "--run-name",
            "quick local",
        ]
    )

    captured = capfd.readouterr()
    assert result == 0
    run_dir_line = next(line for line in captured.out.splitlines() if line.startswith("run_dir: "))
    run_dir = Path(run_dir_line.removeprefix("run_dir: "))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["execution_backend"] == "local_inprocess"
    assert manifest["local_runtime"]["sam3_device"] == "cpu"
    assert manifest["local_runtime"]["rmbg_device"] == "cpu"


def test_cli_run_image_shorthand_local_cpu_profile_overrides_auto_devices(tmp_path: Path, capfd):
    from drawai.cli import main

    image = tmp_path / "input.png"
    Image.new("RGB", (64, 64), "white").save(image)
    base_config = tmp_path / "config.yaml"
    base_config.write_text(
        """
input:
  image: placeholder.png
  output_dir: placeholder_out
  normalization:
    enabled: false
sam3:
  mode: fixture
  fixture:
    path: sam3.json
ocr:
  mode: fixture
  fixture:
    path: ocr.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: false
""",
        encoding="utf-8",
    )

    result = main(
        [
            "run",
            str(image),
            "--local",
            "--dry-run",
            "--base-config",
            str(base_config),
            "--run-root",
            str(tmp_path / "runs"),
            "--run-name",
            "quick local",
            "--profile",
            "local-cpu",
        ]
    )

    captured = capfd.readouterr()
    assert result == 0
    run_dir_line = next(line for line in captured.out.splitlines() if line.startswith("run_dir: "))
    run_dir = Path(run_dir_line.removeprefix("run_dir: "))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["local_runtime"]["sam3_device"] == "cpu"
    assert manifest["local_runtime"]["rmbg_device"] == "cpu"


def test_cli_run_image_shorthand_device_gpu_maps_torch_models_to_cuda(tmp_path: Path, capfd):
    from drawai.cli import main

    image = tmp_path / "input.png"
    Image.new("RGB", (64, 64), "white").save(image)
    base_config = tmp_path / "config.yaml"
    base_config.write_text(
        """
input:
  image: placeholder.png
  output_dir: placeholder_out
sam3:
  mode: fixture
  fixture:
    path: sam3.json
ocr:
  mode: fixture
  fixture:
    path: ocr.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: false
""",
        encoding="utf-8",
    )

    result = main(
        [
            "run",
            str(image),
            "--local",
            "--dry-run",
            "--device",
            "gpu",
            "--base-config",
            str(base_config),
            "--run-root",
            str(tmp_path / "runs"),
        ]
    )

    captured = capfd.readouterr()
    assert result == 0
    run_dir_line = next(line for line in captured.out.splitlines() if line.startswith("run_dir: "))
    run_dir = Path(run_dir_line.removeprefix("run_dir: "))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["local_runtime"]["sam3_device"] == "cuda"
    assert manifest["local_runtime"]["rmbg_device"] == "cuda"
    assert manifest["local_runtime"]["paddle_device"] == "cpu"


def test_cli_run_image_shorthand_device_mps_keeps_sam3_on_cpu(tmp_path: Path, capfd):
    from drawai.cli import main

    image = tmp_path / "input.png"
    Image.new("RGB", (64, 64), "white").save(image)
    base_config = tmp_path / "config.yaml"
    base_config.write_text(
        """
input:
  image: placeholder.png
  output_dir: placeholder_out
sam3:
  mode: fixture
  fixture:
    path: sam3.json
ocr:
  mode: fixture
  fixture:
    path: ocr.json
asset_materialization:
  rmbg:
    enabled: false
svg_to_ppt:
  enabled: false
""",
        encoding="utf-8",
    )

    result = main(
        [
            "run",
            str(image),
            "--local",
            "--dry-run",
            "--device",
            "mps",
            "--base-config",
            str(base_config),
            "--run-root",
            str(tmp_path / "runs"),
        ]
    )

    captured = capfd.readouterr()
    assert result == 0
    run_dir_line = next(line for line in captured.out.splitlines() if line.startswith("run_dir: "))
    run_dir = Path(run_dir_line.removeprefix("run_dir: "))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["local_runtime"]["sam3_device"] == "cpu"
    assert manifest["local_runtime"]["rmbg_device"] == "mps"
    assert manifest["local_runtime"]["paddle_device"] == "cpu"


def test_pipeline_missing_input_image_writes_failed_summary(tmp_path: Path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
input:
  image: missing.png
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

    summary = run_drawai_pipeline(config)

    summary_path = tmp_path / "out" / "reports" / "pipeline_summary.json"
    stage_status_path = tmp_path / "out" / "reports" / "stage_status.json"
    assert summary["status"] == "failed"
    assert summary["failed_stage"] == "input_normalized"
    assert summary_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["status"] == "failed"

    stage_status = json.loads(stage_status_path.read_text(encoding="utf-8"))
    assert stage_status["latest_stage"] == "input_normalized"
    assert stage_status["latest_status"] == "failed"


def test_pipeline_uses_default_codex_python_sdk_invoker(monkeypatch, tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 1
svg_to_ppt:
  enabled: true
  export_pptx: false
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text('{"ocr_text_boxes":[]}', encoding="utf-8")
    calls = []

    class FakeSam3Transport:
        def post_json(self, path, payload, timeout_s):
            return {
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    sessions = []

    class FakeCodexPythonSdkSvgSession:
        def __init__(
            self,
            *,
            runtime_config,
            trace_path,
            isolated_cwd=None,
            config_overrides=None,
            shared_prompt=None,
        ):
            self.runtime_config = runtime_config
            self.trace_path = str(trace_path)
            self.isolated_cwd = str(isolated_cwd) if isolated_cwd is not None else None
            self.config_overrides = list(config_overrides or ())
            self.shared_prompt = shared_prompt or ""
            self.closed = False
            sessions.append(self)

        def __enter__(self):
            return self

        def close(self):
            self.closed = True

        def invoke(
            self,
            *,
            image_paths,
            prompt,
            task_name,
            output_svg_path=None,
            output_response_path=None,
        ):
            calls.append(
                {
                    "image_paths": [str(path) for path in image_paths],
                    "prompt": prompt,
                    "task_name": task_name,
                    "output_svg_path": str(output_svg_path) if output_svg_path is not None else None,
                    "output_response_path": str(output_response_path) if output_response_path is not None else None,
                }
            )
            if task_name == "box_ir_semantic_svg.codex_merged_stages.v1":
                attempt_dir = Path(output_svg_path).parent
                attempt_dir.mkdir(parents=True, exist_ok=True)
                (attempt_dir / "iteration_log.md").write_text(
                    "# Codex SVG self-iteration log\n\n- merged template/review/refine\n",
                    encoding="utf-8",
                )
                (attempt_dir / "iteration_log.jsonl").write_text(
                    '{"iteration":0,"stage":"template","svg":"semantic_0.svg","rendered":"rendered_0.png"}\n',
                    encoding="utf-8",
                )
                return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="80" cy="40" r="8" fill="red"/></svg>'
            raise AssertionError(task_name)

    monkeypatch.setattr(
        "drawai.codex_python_sdk_svg.CodexPythonSdkSvgSession",
        FakeCodexPythonSdkSvgSession,
    )

    summary = run_drawai_pipeline(config, sam3_transport=FakeSam3Transport())

    assert summary["status"] == "ok"
    assert len(sessions) == 1
    assert sessions[0].closed is True
    assert [call["task_name"] for call in calls] == ["box_ir_semantic_svg.codex_merged_stages.v1"]
    assert sessions[0].runtime_config["provider"] == "codex-python-sdk"
    assert sessions[0].runtime_config["connection_id"] == "codex-python-sdk-controlled"
    assert sessions[0].runtime_config["model_name"] == ""
    assert sessions[0].runtime_config["base_url"] == ""
    assert sessions[0].runtime_config["timeout_seconds"] == 1500
    assert sessions[0].isolated_cwd.endswith("/out")
    assert calls[0]["output_svg_path"].endswith("/svg/attempts/codex_merged/001/semantic.svg")
    assert calls[0]["output_response_path"].endswith("/svg/attempts/codex_merged/001/model_response.txt")
    assert len(calls[0]["image_paths"]) == 2
    assert calls[0]["image_paths"][0].endswith("/inputs/figure.png")
    assert calls[0]["image_paths"][1].endswith("/svg/template_reference.png")
    shared_prompt_file = tmp_path / "out" / "svg" / "codex_thread_shared_prompt.txt"
    assert shared_prompt_file.exists()
    shared_prompt_text = shared_prompt_file.read_text(encoding="utf-8")
    assert shared_prompt_text == sessions[0].shared_prompt
    assert "DRAWAI CODEX THREAD SHARED CONTEXT" in shared_prompt_text
    assert "MUST READ FILES" in shared_prompt_text
    assert "WORKSPACE RULES" in shared_prompt_text
    assert "layout IR JSON: box_ir/box_ir.json" in shared_prompt_text
    prompt_file = (
        tmp_path
        / "out"
        / "svg"
        / "attempts"
        / "codex_merged"
        / "001"
        / "prompt.txt"
    )
    context_file = (
        tmp_path
        / "out"
        / "svg"
        / "attempts"
        / "codex_merged"
        / "001"
        / "request_context.json"
    )
    assert prompt_file.exists()
    prompt_text = prompt_file.read_text(encoding="utf-8")
    assert context_file.exists()
    context = json.loads(context_file.read_text(encoding="utf-8"))
    assert context["phase"] == "codex_merged_stages"
    assert context["visual_review_rounds"] == ["text_style"]
    assert context["iteration_log"].endswith("/svg/attempts/codex_merged/001/iteration_log.md")
    assert context["iteration_log_jsonl"].endswith("/svg/attempts/codex_merged/001/iteration_log.jsonl")
    assert context["reference_image_path"].endswith("/svg/template_reference.png")
    assert "IMAGE VECTORIZATION TASK" in prompt_text
    assert "AVAILABLE FILES AND READING LOGIC" in prompt_text
    assert "OVERALL DRAWAI PIPELINE" in prompt_text
    assert "RUN1 / COMPLETE FIRST PASS" in prompt_text
    assert "REFINE LOOP / MAX 3 ROUNDS" in prompt_text
    assert "Run 2 / visual_review_text_style" not in prompt_text
    assert "Run 3 / ir_refine" not in prompt_text
    assert "semantic_0.svg" in prompt_text
    assert "semantic_3.svg" in prompt_text
    assert "rendered_0.png" in prompt_text
    assert "iteration_log.md" in prompt_text
    assert "The whole-figure render is perfectly close to the original" in prompt_text
    assert "Another round is likely to make the figure better" in prompt_text
    assert "FINAL CHECK BEFORE ENDING THIS TURN" in prompt_text
    assert "MUST READ FILES" not in prompt_text
    assert "WORKSPACE RULES" not in prompt_text
    assert "OUTPUT CONTRACT" not in prompt_text
    assert "Compact Template IR JSON" not in calls[0]["prompt"]
    assert "Attempt feedback JSON" not in calls[0]["prompt"]
    assert "Attempt feedback source" in calls[0]["prompt"]
    assert "RUN1 / COMPLETE FIRST PASS" in calls[0]["prompt"]
    assert "REFINE LOOP / MAX 3 ROUNDS" in calls[0]["prompt"]
    assert "Run1 and every refine round may use allowed local raster image hrefs" in calls[0]["prompt"]
    assert "Current template SVG to refine:\n<svg" not in calls[0]["prompt"]
    assert "Validated visual template SVG from stage 1:\n<svg" not in calls[0]["prompt"]
    assert "layout IR JSON with OCR text redacted" not in calls[0]["prompt"]
    assert "layout IR JSON: box_ir/box_ir.json" in calls[0]["prompt"]
    assert "Asset Placeholder Plan JSON" not in calls[0]["prompt"]
    assert (tmp_path / "out" / "svg" / "attempts" / "codex_merged" / "001" / "iteration_log.md").exists()
    assert (tmp_path / "out" / "svg" / "attempts" / "codex_merged" / "001" / "iteration_log.jsonl").exists()


def test_failed_rerun_clears_stale_later_stage_status_and_artifacts(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 1
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="80" cy="40" r="8" fill="red"/></svg>'

    first = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=svg_invoker,
    )
    assert first["status"] == "ok"
    semantic_svg = tmp_path / "out" / "svg" / "semantic.svg"
    assert semantic_svg.exists()

    image.unlink()
    second = run_drawai_pipeline(config)

    assert second["status"] == "failed"
    assert second["failed_stage"] == "input_normalized"
    assert not semantic_svg.exists()
    stage_status = json.loads((tmp_path / "out" / "reports" / "stage_status.json").read_text(encoding="utf-8"))
    assert stage_status["latest_stage"] == "input_normalized"
    assert stage_status["latest_status"] == "failed"
    assert "svg_generated" not in stage_status["stages"]


def test_failed_rerun_clears_stale_first_class_generated_artifacts(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
svg:
  max_attempts: 1
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def svg_invoker(**kwargs):
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 50" width="100" height="50"><rect width="100" height="50" fill="white"/><circle cx="80" cy="40" r="8" fill="red"/></svg>'

    first = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=svg_invoker,
    )
    assert first["status"] == "ok"

    stale_paths = [
        tmp_path / "out" / "inputs" / "original.png",
        tmp_path / "out" / "inputs" / "figure.png",
        tmp_path / "out" / "inputs" / "source_metadata.json",
        tmp_path / "out" / "sam3" / "raw_regions.json",
        tmp_path / "out" / "trace" / "model.jsonl",
        tmp_path / "out" / "svg_to_ppt" / "stale.pptx",
        tmp_path / "out" / "svg" / "asset_recovery_reference.png",
        tmp_path / "out" / "svg" / "asset_recovery_reference_legend.png",
        tmp_path / "out" / "svg" / "asset_recovery_reference_legend.json",
        tmp_path / "out" / "svg" / "template_iterations" / "stale.svg",
    ]
    for stale_path in stale_paths:
        stale_path.parent.mkdir(parents=True, exist_ok=True)
        stale_path.write_bytes(b"stale-run-content")

    image.unlink()
    second = run_drawai_pipeline(config)

    assert second["status"] == "failed"
    assert second["failed_stage"] == "input_normalized"
    for stale_path in stale_paths:
        assert not stale_path.exists(), stale_path


def test_svg_generation_error_metadata_is_written_to_failed_summary(monkeypatch, tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def fake_run_svg_generation_loop(**kwargs):
        raise SvgGenerationError(
            "bad svg",
            {
                "attempt_reports": [{"attempt": 1, "status": "failed"}],
                "last_issues": [{"code": "missing_svg_output"}],
                "custom": "kept",
            },
        )

    monkeypatch.setattr(
        "drawai.pipeline.run_svg_generation_loop",
        fake_run_svg_generation_loop,
    )
    summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=lambda **kwargs: "<svg/>",
    )

    assert summary["status"] == "failed"
    assert summary["exception"]["svg_generation"]["last_issues"] == [{"code": "missing_svg_output"}]
    assert summary["exception"]["svg_generation"]["metadata"]["custom"] == "kept"


def test_failure_summary_redacts_secret_and_base64_patterns(monkeypatch, tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (100, 50), "white").save(image)
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
    raw_base64 = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
    raw_payload_base64 = "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo="
    raw_basic_auth = "dXNlcjpwYXNz"
    secret_text = (
        "Authorization: Bearer SECRET api_key=SECRET "
        "x-api-key: SECRET "
        "api-key: SECRET4 "
        "Authorization: Token SECRET2 "
        f"Authorization: Basic {raw_basic_auth} "
        f"payload={raw_payload_base64} "
        f"data:image/png;base64,{raw_base64}"
    )

    class FakeSam3Transport:
        def post_json(self, path, payload, timeout_s):
            return {
                "regions": [{"bbox": [10, 10, 40, 30], "score": 0.9, "label": "icon"}],
                "raw_regions": [],
            }, 1.0

    def fake_run_svg_generation_loop(**kwargs):
        raise SvgGenerationError(
            f"bad svg {secret_text}",
            {
                "attempt_reports": [{"attempt": 1, "detail": secret_text}],
                "last_issues": [{"code": "runtime_error", "detail": secret_text}],
                "metadata_string": secret_text,
                "payload_detail": f"provider returned payload={raw_payload_base64}",
                "payload": raw_payload_base64,
                "headers": {
                    "x-api-key": "SECRET",
                    "api-key": "SECRET3",
                    "ordinary": "kept",
                },
            },
        )

    monkeypatch.setattr(
        "drawai.pipeline.run_svg_generation_loop",
        fake_run_svg_generation_loop,
    )

    summary = run_drawai_pipeline(
        config,
        sam3_transport=FakeSam3Transport(),
        svg_invoker=lambda **kwargs: "<svg/>",
    )

    assert summary["status"] == "failed"
    persisted = (tmp_path / "out" / "reports" / "pipeline_summary.json").read_text(encoding="utf-8")
    assert "SECRET" not in persisted
    assert "SECRET2" not in persisted
    assert "SECRET3" not in persisted
    assert "SECRET4" not in persisted
    assert raw_basic_auth not in persisted
    assert raw_payload_base64 not in persisted
    assert raw_base64 not in persisted
    assert "data:image/png;base64" not in persisted
    stage_status = (tmp_path / "out" / "reports" / "stage_status.json").read_text(encoding="utf-8")
    assert "SECRET" not in stage_status
    assert "SECRET2" not in stage_status
    assert "SECRET3" not in stage_status
    assert "SECRET4" not in stage_status
    assert raw_basic_auth not in stage_status
    assert raw_payload_base64 not in stage_status
    assert raw_base64 not in stage_status
    assert "data:image/png;base64" not in stage_status
    assert '"ordinary": "kept"' in persisted
