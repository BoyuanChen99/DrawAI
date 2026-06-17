import asyncio
import json
import types
from pathlib import Path

from PIL import Image

from drawai.artifacts import prepare_artifact_paths
from drawai.codex_svg_tool_loop import (
    SUBMIT_SVG_TOOL_NAME,
    _build_input_payload,
    _extract_svg_from_stream,
    _model_input_image_bytes,
    extract_svg_from_response,
)
from drawai.config import (
    DrawAiInputConfig,
    DrawAiPipelineConfig,
    DrawAiSvgConfig,
    ModelRuntimeConfig,
)
from drawai.pipeline import _default_svg_invoker


def test_extract_svg_from_submit_tool_call():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    response = {
        "output": [
            {"type": "reasoning", "summary": []},
            {
                "type": "function_call",
                "name": SUBMIT_SVG_TOOL_NAME,
                "arguments": json.dumps({"svg": svg}),
            },
        ]
    }

    extracted, metadata = extract_svg_from_response(response)

    assert extracted == svg
    assert metadata == {"source": "tool_call", "tool": SUBMIT_SVG_TOOL_NAME}


def test_extract_svg_falls_back_to_output_text_object():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    response = types.SimpleNamespace(output_text=svg, output=[])

    extracted, metadata = extract_svg_from_response(response)

    assert extracted == svg
    assert metadata == {"source": "output_text"}


def test_extract_svg_from_stream_output_item_done():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    stream = _FakeAsyncStream(
        [
            types.SimpleNamespace(
                type="response.output_item.done",
                item={
                    "type": "function_call",
                    "name": SUBMIT_SVG_TOOL_NAME,
                    "arguments": json.dumps({"svg": svg}),
                },
            )
        ]
    )

    extracted, metadata = asyncio.run(_extract_svg_from_stream(stream))

    assert extracted == svg
    assert metadata == {"source": "stream_output_item_done", "tool": SUBMIT_SVG_TOOL_NAME}


class _FakeAsyncStream:
    def __init__(self, events):
        self._events = list(events)
        self.closed = False

    def __aiter__(self):
        self._iterator = iter(self._events)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration as exc:
            raise StopAsyncIteration from exc

    async def close(self):
        self.closed = True


def test_sdk_input_marks_tool_contract_as_internal(tmp_path):
    image_path = tmp_path / "input.png"
    image_path.write_bytes(b"png")

    payload, image_traces = _build_input_payload(prompt="Generate SVG.", image_paths=[image_path])

    assert payload[0]["type"] == "message"
    assert payload[0]["role"] == "user"
    text = payload[0]["content"][0]["text"]
    assert "internal pipeline protocol" in text
    assert "not a user-role command" in text
    assert "starting with <svg and ending with </svg>" in text
    assert "Do not wrap the SVG in JSON, Markdown fences, commentary, or analysis text" in text
    assert payload[0]["content"][1]["type"] == "input_image"
    assert image_traces[0]["image_path"] == str(image_path)


def test_large_sdk_input_image_is_compressed_for_model(tmp_path):
    image_path = tmp_path / "large.png"
    Image.effect_noise((1800, 1200), 80).convert("RGB").save(image_path)
    original_bytes = image_path.read_bytes()

    encoded_bytes, mime_type, encoding = _model_input_image_bytes(image_path, original_bytes)

    assert mime_type == "image/jpeg"
    assert encoding == "jpeg_quality_90"
    assert len(encoded_bytes) < len(original_bytes)


def test_default_svg_invoker_routes_sdk_tool_loop(monkeypatch, tmp_path):
    figure = tmp_path / "figure.png"
    reference = tmp_path / "reference.png"
    figure.write_bytes(b"figure")
    reference.write_bytes(b"reference")
    paths = prepare_artifact_paths(tmp_path / "artifacts")
    cfg = DrawAiPipelineConfig(
        input=DrawAiInputConfig(image=Path("input.png"), output_dir=tmp_path / "out"),
        svg=DrawAiSvgConfig(generation_backend="sdk_tool_loop"),
        model_runtime=ModelRuntimeConfig(provider="local-codex-gateway", connection_id="local-codex-gateway"),
    )
    calls = []

    def fake_invoke_codex_svg_text(**kwargs):
        calls.append(kwargs)
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'

    monkeypatch.setattr(
        "drawai.codex_svg_tool_loop.invoke_codex_svg_text",
        fake_invoke_codex_svg_text,
    )

    invoker = _default_svg_invoker(cfg, paths)
    result = invoker(
        figure_path=figure,
        reference_image_path=reference,
        box_ir={"canvas": {"width": 10, "height": 10}},
        asset_manifest={"assets": []},
        phase="template",
    )

    assert result.startswith("<svg")
    assert calls
    assert calls[0]["task_name"] == "box_ir_semantic_svg.template.v1"
    assert calls[0]["runtime_config"]["model_name"] == ""
