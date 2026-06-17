import base64
import io

import pytest
from PIL import Image

from drawai.rmbg_client import RemoteRmbgClient, RmbgResponseError


def _encoded_png(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_remote_rmbg_client_uses_agent_service_contract():
    returned = Image.new("RGBA", (2, 2), (10, 20, 30, 128))

    class FakeTransport:
        def __init__(self):
            self.calls = []

        def post_json(self, path, payload, timeout_s):
            self.calls.append({"path": path, "payload": payload, "timeout_s": timeout_s})
            return {
                "image_base64": _encoded_png(returned),
                "artifacts": {"nobg": "/v1/segment/artifacts/rmbg/icon_AF01_nobg.png"},
            }, 4.25

    transport = FakeTransport()
    client = RemoteRmbgClient("http://127.0.0.1:18080", transport=transport)

    result = client.remove_background(
        Image.new("RGB", (2, 2), "white"),
        "AF01",
        timeout_s=17,
        model_path="/opt/drawai/models/rmbg",
        artifact_prefix="drawai_assets/AF01",
    )

    assert transport.calls[0]["path"] == "/v1/rmbg/remove-background"
    request = transport.calls[0]["payload"]
    assert request["output_name"] == "AF01"
    assert request["return_image"] is True
    assert request["model_path"] == "/opt/drawai/models/rmbg"
    assert request["artifact_prefix"] == "drawai_assets/AF01"
    assert request["image_base64"]
    assert transport.calls[0]["timeout_s"] == 17
    assert result.image.mode == "RGBA"
    assert result.image.size == (2, 2)
    assert result.artifacts == {"nobg": "/v1/segment/artifacts/rmbg/icon_AF01_nobg.png"}
    assert result.elapsed_ms == 4.25


def test_remote_rmbg_client_rejects_missing_image_payload():
    class FakeTransport:
        def post_json(self, path, payload, timeout_s):
            return {"artifacts": {}}, 1.0

    client = RemoteRmbgClient("http://127.0.0.1:18080", transport=FakeTransport())

    with pytest.raises(RmbgResponseError, match="image_base64"):
        client.remove_background(Image.new("RGB", (2, 2), "white"), "AF01", timeout_s=1)
