import json
from pathlib import Path

from PIL import Image

from drawai.artifacts import prepare_artifact_paths
from drawai.config import load_drawai_config
from drawai.image_normalization import normalize_input_image


def _write_png(path: Path, size=(100, 50), mode="RGB"):
    image = Image.new(mode, size, (255, 0, 0, 128) if mode == "RGBA" else (255, 0, 0))
    image.save(path)


def test_prepare_artifact_paths_uses_spec_artifact_names(tmp_path: Path):
    paths = prepare_artifact_paths(tmp_path)
    assert paths.box_ir_raw_json.name == "box_ir.raw.json"
    assert paths.svg_to_ppt_export_report_json.name == "svg_to_ppt_export_report.json"
    assert paths.assets_dir == tmp_path / "svg_to_ppt" / "assets"
    assert paths.crops_dir == tmp_path / "svg_to_ppt" / "assets" / "crops"


def test_normalize_upscales_to_3840_long_edge(tmp_path: Path):
    source = tmp_path / "source.png"
    _write_png(source, size=(100, 50))
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {source.name}
  output_dir: out
  normalization:
    enabled: true
    target_long_edge: 3840
    upscale_only: true
""",
        encoding="utf-8",
    )
    cfg = load_drawai_config(config)
    paths = prepare_artifact_paths(cfg.input.output_dir)
    result = normalize_input_image(cfg.input, paths)
    assert result.original_size == (100, 50)
    assert result.normalized_size == (3840, 1920)
    assert result.scale == 38.4
    assert paths.figure_image.exists()
    assert paths.source_metadata.exists()

    metadata = json.loads(paths.source_metadata.read_text(encoding="utf-8"))
    assert metadata["coordinate_system"] == "figure_image_pixels"
    assert metadata["target_long_edge"] == 3840
    assert metadata["upscaled"] is True


def test_normalize_keeps_large_image_when_upscale_only(tmp_path: Path):
    source = tmp_path / "large.png"
    _write_png(source, size=(4000, 2000))
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {source.name}
  output_dir: out
  normalization:
    enabled: true
    target_long_edge: 3840
    upscale_only: true
""",
        encoding="utf-8",
    )
    cfg = load_drawai_config(config)
    result = normalize_input_image(cfg.input, prepare_artifact_paths(cfg.input.output_dir))
    assert result.normalized_size == (4000, 2000)
    assert result.upscaled is False


def test_normalize_flattens_transparency_to_rgb(tmp_path: Path):
    source = tmp_path / "alpha.png"
    _write_png(source, size=(40, 20), mode="RGBA")
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {source.name}
  output_dir: out
  normalization:
    enabled: false
    flatten_transparency_background: "#ffffff"
""",
        encoding="utf-8",
    )
    cfg = load_drawai_config(config)
    paths = prepare_artifact_paths(cfg.input.output_dir)
    normalize_input_image(cfg.input, paths)
    assert Image.open(paths.figure_image).mode == "RGB"


def test_normalize_flattens_rgb_transparency_key(tmp_path: Path):
    source = tmp_path / "trns.png"
    image = Image.new("RGB", (2, 1), (255, 0, 0))
    image.putpixel((1, 0), (0, 255, 0))
    image.save(source, transparency=(0, 255, 0))
    config = tmp_path / "config.yaml"
    config.write_text(
        f"""
input:
  image: {source.name}
  output_dir: out
  normalization:
    enabled: false
    flatten_transparency_background: "#ffffff"
""",
        encoding="utf-8",
    )
    cfg = load_drawai_config(config)
    paths = prepare_artifact_paths(cfg.input.output_dir)
    normalize_input_image(cfg.input, paths)
    figure = Image.open(paths.figure_image)
    assert figure.mode == "RGB"
    assert figure.getpixel((1, 0)) == (255, 255, 255)
