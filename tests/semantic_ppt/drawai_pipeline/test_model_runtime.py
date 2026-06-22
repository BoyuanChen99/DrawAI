from pathlib import Path
from PIL import Image

from drawai import model_runtime


def test_invoke_vision_text_passes_runtime_timeout(monkeypatch, tmp_path: Path):
    image = tmp_path / "figure.png"
    Image.new("RGB", (4, 4), "white").save(image)
    captured = {}

    async def fake_invoke_openai_compatible_response(**kwargs):
        captured["timeout_seconds"] = kwargs["timeout_seconds"]
        captured["model_name"] = kwargs["settings"].model_name
        return "ok"

    monkeypatch.setattr(model_runtime, "_invoke_openai_compatible_response", fake_invoke_openai_compatible_response)

    result = model_runtime.invoke_vision_text(
        image_paths=[image],
        prompt="describe",
        task_name="timeout_test",
        runtime_config={"provider": "fake", "model_name": "fake-model", "timeout_seconds": 900},
    )

    assert result == "ok"
    assert captured["timeout_seconds"] == 900
    assert captured["model_name"] == "fake-model"


def test_invoke_multimodal_text_allows_text_only(monkeypatch):
    captured = {}

    async def fake_invoke_openai_compatible_response(**kwargs):
        captured["input_content"] = kwargs["input_content"]
        captured["model_name"] = kwargs["settings"].model_name
        return "ok"

    monkeypatch.setattr(model_runtime, "_invoke_openai_compatible_response", fake_invoke_openai_compatible_response)

    result = model_runtime.invoke_multimodal_text(
        image_paths=(),
        prompt="return json",
        task_name="text_only",
        runtime_config={"provider": "fake", "model_name": "fake-model"},
    )

    assert result == "ok"
    assert captured["input_content"] == [{"type": "input_text", "text": "return json"}]
    assert captured["model_name"] == "fake-model"


def test_invoke_multimodal_text_can_use_chat_completions_with_extra_body(monkeypatch):
    captured = {}

    async def fake_chat_completion(**kwargs):
        captured["input_content"] = kwargs["input_content"]
        captured["extra_body"] = kwargs["settings"].extra_body
        captured["wire_api"] = kwargs["settings"].wire_api
        return "ok"

    monkeypatch.setattr(model_runtime, "_invoke_openai_compatible_chat_completion", fake_chat_completion)

    result = model_runtime.invoke_multimodal_text(
        image_paths=(),
        prompt="return json",
        task_name="chat_completion",
        runtime_config={
            "provider": "openrouter",
            "model_name": "minimax/minimax-m3",
            "wire_api": "chat_completions",
            "extra_body": {"reasoning": {"enabled": True}},
        },
    )

    assert result == "ok"
    assert captured["input_content"] == [{"type": "input_text", "text": "return json"}]
    assert captured["extra_body"] == {"reasoning": {"enabled": True}}
    assert captured["wire_api"] == "chat_completions"
