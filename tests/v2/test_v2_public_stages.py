from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from drawai.public_stages import PUBLIC_STAGE_ORDER, run_public_stage


def _config(tmp_path: Path, *, refine_enabled: bool | None = False) -> Path:
    image = tmp_path / "input.png"
    Image.new("RGB", (80, 40), "white").save(image)
    config = tmp_path / "config.yaml"
    v2_section = ""
    if refine_enabled is not None:
        v2_section = f"""
v2:
  refine:
    enabled: {str(refine_enabled).lower()}
"""
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
{v2_section}
""",
        encoding="utf-8",
    )
    (tmp_path / "ocr_fixture.json").write_text(
        '{"ocr_text_boxes":[{"id":"T001","bbox":[4,5,20,14],"text":"Hello","confidence":0.9}]}',
        encoding="utf-8",
    )
    return config


def test_public_stage_order_uses_v2_main_path() -> None:
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


def test_v2_pipeline_writes_run_package_after_fusion(tmp_path: Path) -> None:
    summary = run_public_stage(_config(tmp_path), "fuse_elements")

    assert summary["status"] == "ok"
    package_path = Path(summary["artifacts"]["run_package"])
    assert package_path.is_file()
    payload = json.loads(package_path.read_text(encoding="utf-8"))
    assert payload["schema"] == "drawai.run_package.v1"
    assert payload["elements"]


def test_refine_disabled_allows_deterministic_skip_trace(tmp_path: Path) -> None:
    summary = run_public_stage(_config(tmp_path, refine_enabled=False), "refine_elements")

    assert summary["status"] == "ok"
    trace = json.loads(Path(summary["artifacts"]["v2_refine_trace"]).read_text(encoding="utf-8"))
    assert trace["status"] == "skipped"
    assert trace["provider"] == "codex_element_refiner"


def test_refine_enabled_requires_refinement_artifact(tmp_path: Path) -> None:
    summary = run_public_stage(_config(tmp_path, refine_enabled=None), "refine_elements")

    assert summary["status"] == "failed"
    assert summary["failed_stage"] == "refine_elements"
    assert "Codex element refinement analysis" in summary["exception"]["message"]
