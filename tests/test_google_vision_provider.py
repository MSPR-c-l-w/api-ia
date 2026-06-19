"""Tests unitaires de GoogleVisionProvider (urllib simulé)."""

import json
from urllib.error import URLError

from app.contexts.nutrition.infrastructure.vision import google_vision_provider
from app.contexts.nutrition.infrastructure.vision.google_vision_provider import (
    GoogleVisionProvider,
)


class _FakeResponse:
    def __init__(self, content: str):
        self._content = content.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._content


def _patch_urlopen(monkeypatch, *, content=None, raise_exc=None):
    def fake_urlopen(req, timeout=None):
        if raise_exc is not None:
            raise raise_exc
        return _FakeResponse(content)

    monkeypatch.setattr(google_vision_provider.request, "urlopen", fake_urlopen)


async def test_no_endpoint_returns_empty():
    provider = GoogleVisionProvider(endpoint=None, api_key=None)

    assert await provider.detect_foods("http://img", None) == []


async def test_parses_foods_dict_shape(monkeypatch):
    content = json.dumps(
        {
            "foods": [
                {"label": "salade", "confidence": 0.91},
                {"label": "tomate", "confidence": 0.8},
            ]
        }
    )
    _patch_urlopen(monkeypatch, content=content)
    provider = GoogleVisionProvider(endpoint="http://vision", api_key="k")

    detections = await provider.detect_foods(None, "base64data")

    assert [d.label for d in detections] == ["salade", "tomate"]
    assert detections[0].confidence == 0.91


async def test_parses_list_shape_with_score(monkeypatch):
    content = json.dumps([{"label": "poulet", "score": 0.77}])
    _patch_urlopen(monkeypatch, content=content)
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    detections = await provider.detect_foods("http://img", None)

    assert detections[0].label == "poulet"
    assert detections[0].confidence == 0.77


async def test_skips_non_dict_items(monkeypatch):
    content = json.dumps({"foods": ["bad", {"label": "riz", "confidence": 0.6}]})
    _patch_urlopen(monkeypatch, content=content)
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    detections = await provider.detect_foods("http://img", None)

    assert len(detections) == 1
    assert detections[0].label == "riz"


async def test_skips_non_dict_items_in_list_shape(monkeypatch):
    content = json.dumps(["bad", {"label": "riz", "score": 0.6}])
    _patch_urlopen(monkeypatch, content=content)
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    detections = await provider.detect_foods("http://img", None)

    assert len(detections) == 1
    assert detections[0].label == "riz"


async def test_unknown_shape_returns_empty(monkeypatch):
    _patch_urlopen(monkeypatch, content=json.dumps({"unexpected": True}))
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    assert await provider.detect_foods("http://img", None) == []


async def test_network_error_returns_empty(monkeypatch):
    _patch_urlopen(monkeypatch, raise_exc=URLError("boom"))
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    assert await provider.detect_foods("http://img", None) == []


async def test_invalid_json_returns_empty(monkeypatch):
    _patch_urlopen(monkeypatch, content="not json")
    provider = GoogleVisionProvider(endpoint="http://vision", api_key=None)

    assert await provider.detect_foods("http://img", None) == []
