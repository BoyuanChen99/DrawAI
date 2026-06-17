from pathlib import Path

from drawai.artifacts import prepare_artifact_paths
from drawai.config import DrawAiInputConfig, DrawAiPipelineConfig, DrawAiSvgToPptConfig
from drawai.pipeline import _check_svg_to_ppt


def test_export_stage_calls_svg_to_ppt_without_compatibility_profile(tmp_path: Path):
    paths = prepare_artifact_paths(tmp_path / "out")
    paths.semantic_svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 80">'
        '<defs><filter id="shadow"><feDropShadow dx="1" dy="1"/></filter></defs>'
        '<rect width="20" height="20" filter="url(#shadow)"/></svg>',
        encoding="utf-8",
    )
    cfg = DrawAiPipelineConfig(
        input=DrawAiInputConfig(image=tmp_path / "input.png", output_dir=paths.root),
        svg_to_ppt=DrawAiSvgToPptConfig(),
    )
    seen: dict[str, Path] = {}

    def compiler(svg_path: Path, output_pptx: Path):
        seen["svg_path"] = svg_path
        seen["output_pptx"] = output_pptx
        output_pptx.write_bytes(b"pptx")
        return {"backend": "drawai_native_shapes", "editable_surface": "native_shapes"}

    report = _check_svg_to_ppt(cfg, paths, asset_manifest={"assets": []}, compiler=compiler)

    assert seen["svg_path"] == paths.semantic_svg
    assert seen["output_pptx"] == paths.root / "svg_to_ppt" / "semantic.svg_to_ppt.pptx"
    assert report["status"] == "ok"
    assert report["export_backend"] == "drawai_native_shapes"
    assert report["effective_export_mode"] == "native_shapes"
    assert report["export_mode"] == "native_shapes"
