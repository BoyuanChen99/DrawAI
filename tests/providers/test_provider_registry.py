from __future__ import annotations

from dataclasses import dataclass

import pytest

from drawai.providers import ProviderEntry, ProviderLookupError, ProviderRegistry


@dataclass(frozen=True)
class FakeOcrProvider:
    value: str = "ocr"


@dataclass(frozen=True)
class FakeSamProvider:
    value: str = "sam"


def test_provider_registry_returns_provider_by_name():
    registry = ProviderRegistry()
    provider = FakeOcrProvider()

    registry.register(ProviderEntry(name="ocr.local", protocol="OcrDetector", provider=provider))

    assert registry.require("ocr.local") is provider


def test_provider_registry_lists_provider_names_by_protocol():
    registry = ProviderRegistry(
        [
            ProviderEntry(name="ocr.local", protocol="OcrDetector", provider=FakeOcrProvider()),
            ProviderEntry(name="sam.local", protocol="SamDetector", provider=FakeSamProvider()),
            ProviderEntry(name="ocr.fixture", protocol="OcrDetector", provider=FakeOcrProvider("fixture")),
        ]
    )

    assert registry.names_for_protocol("OcrDetector") == ["ocr.fixture", "ocr.local"]
    assert registry.names_for_protocol("SamDetector") == ["sam.local"]


def test_provider_registry_rejects_duplicate_names():
    with pytest.raises(ValueError, match="duplicate provider name"):
        ProviderRegistry(
            [
                ProviderEntry(name="ocr.local", protocol="OcrDetector", provider=FakeOcrProvider()),
                ProviderEntry(name="ocr.local", protocol="OcrDetector", provider=FakeOcrProvider()),
            ]
        )


def test_provider_registry_require_raises_lookup_error_for_missing_provider():
    registry = ProviderRegistry()

    with pytest.raises(ProviderLookupError) as exc_info:
        registry.require("ocr.local")

    assert exc_info.value.provider_name == "ocr.local"
    assert "ocr.local" in str(exc_info.value)
