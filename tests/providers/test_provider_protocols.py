from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from drawai.ocr_provider import FixtureOcrBoxProvider
from drawai.providers import BackgroundRemover, JsonPostTransport, OcrDetector, PptExporter, SvgGenerator
from drawai.rmbg_client import RmbgResult


class FakeTransport:
    def post_json(self, path: str, payload: dict[str, Any], timeout_s: float) -> tuple[dict[str, Any], float]:
        return {"path": path, "payload": payload, "timeout_s": timeout_s}, 1.0


class FakeBackgroundRemover:
    def remove_background(
        self,
        image: Image.Image,
        output_name: str,
        *,
        timeout_s: float,
        model_path: str = "",
        artifact_prefix: str | None = None,
    ) -> RmbgResult:
        del output_name, timeout_s, model_path, artifact_prefix
        return RmbgResult(image=image.convert("RGBA"), artifacts={}, elapsed_ms=1.0)


def test_existing_fixture_ocr_provider_satisfies_ocr_detector_protocol(tmp_path: Path):
    fixture = tmp_path / "ocr.json"
    fixture.write_text('{"ocr_text_boxes":[]}', encoding="utf-8")

    assert isinstance(FixtureOcrBoxProvider(fixture), OcrDetector)


def test_provider_protocols_match_current_adapter_shapes():
    def svg_generator(**_kwargs):
        return "<svg></svg>"

    def ppt_exporter(_svg_path: Path, _output_path: Path) -> dict[str, str]:
        return {"status": "ok"}

    assert isinstance(FakeTransport(), JsonPostTransport)
    assert isinstance(FakeBackgroundRemover(), BackgroundRemover)
    assert isinstance(svg_generator, SvgGenerator)
    assert isinstance(ppt_exporter, PptExporter)
