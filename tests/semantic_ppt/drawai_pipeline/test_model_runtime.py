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
