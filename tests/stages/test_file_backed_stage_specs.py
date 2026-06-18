from __future__ import annotations

from pathlib import Path

from PIL import Image

from drawai.artifacts import prepare_artifact_paths
from drawai.config import load_drawai_config
from drawai.core import DagRunner
from drawai.stages import build_file_backed_run_context, build_file_backed_stage_specs


def test_file_backed_stage_specs_expose_v2_order_dependencies_and_outputs():
    specs = build_file_backed_stage_specs(["compose_svg", "export"])

    assert [spec.stage_id for spec in specs] == ["compose_svg", "export"]
    assert specs[0].depends_on == ()
    assert specs[1].depends_on == ("compose_svg",)
    assert "semantic_svg" in specs[0].outputs
    assert "rendered_png" in specs[0].outputs
    assert "svg_to_ppt_export_report" in specs[1].outputs
    assert [spec.stage_id for spec in DagRunner(specs).topological_order()] == [
        "compose_svg",
        "export",
    ]


def test_file_backed_stage_spec_runs_v2_prepare_stage_with_real_artifacts(tmp_path: Path):
    image = tmp_path / "input.png"
    Image.new("RGB", (64, 32), "white").save(image)
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
    cfg = load_drawai_config(config)
    paths = prepare_artifact_paths(cfg.input.output_dir)
    context = build_file_backed_run_context(cfg, paths)
    runner = DagRunner(build_file_backed_stage_specs(["prepare"]))

    results = runner.run(context)

    assert [result.stage_id for result in results] == ["prepare"]
    assert results[0].artifacts["figure_image"].exists
    assert results[0].artifacts["source_metadata"].exists
