"""Tests unitaires d'OllamaVisionProvider (httpx simulé — aucun Ollama réel)."""

import json

import httpx

from app.contexts.nutrition.infrastructure.vision import ollama_vision_provider
from app.contexts.nutrition.infrastructure.vision.ollama_vision_provider import (
    OllamaVisionProvider,
)


class _FakeAsyncClient:
    """Faux httpx.AsyncClient : sert ``post`` (/api/chat) et ``get`` (image)."""

    def __init__(
        self,
        *,
        chat_content: str = "{}",
        image_bytes: bytes = b"image-bytes",
        raise_post: Exception | None = None,
        raise_get: Exception | None = None,
    ):
        self._chat_content = chat_content
        self._image_bytes = image_bytes
        self._raise_post = raise_post
        self._raise_get = raise_get
        self.post_calls: list[dict] = []

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None):
        if self._raise_post is not None:
            raise self._raise_post
        self.post_calls.append(json or {})
        req = httpx.Request("POST", url)
        return httpx.Response(
            200, json={"message": {"content": self._chat_content}}, request=req
        )

    async def get(self, url, headers=None, follow_redirects=False):
        if self._raise_get is not None:
            raise self._raise_get
        req = httpx.Request("GET", url)
        return httpx.Response(200, content=self._image_bytes, request=req)


def _patch(monkeypatch, **kwargs) -> _FakeAsyncClient:
    fake = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(ollama_vision_provider.httpx, "AsyncClient", fake)
    return fake


# ---------------------------------------------------------------------------
# Garde-fous (fail-open)
# ---------------------------------------------------------------------------


async def test_no_endpoint_returns_empty():
    provider = OllamaVisionProvider(endpoint=None)

    assert await provider.detect_foods("http://img", None) == []


async def test_no_image_returns_empty(monkeypatch):
    _patch(monkeypatch)
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods(None, None) == []


# ---------------------------------------------------------------------------
# Détection nominale
# ---------------------------------------------------------------------------


async def test_parses_foods_from_base64(monkeypatch):
    content = json.dumps(
        {
            "foods": [
                {"label": "poulet", "confidence": 0.93},
                {"label": "riz", "confidence": 0.88},
            ]
        }
    )
    fake = _patch(monkeypatch, chat_content=content)
    provider = OllamaVisionProvider(endpoint="http://ollama:11434", model="llava")

    detections = await provider.detect_foods(None, "base64data")

    assert [d.label for d in detections] == ["poulet", "riz"]
    assert detections[0].confidence == 0.93
    # L'image base64 fournie est transmise telle quelle au modèle.
    assert fake.post_calls[0]["messages"][0]["images"] == ["base64data"]
    assert fake.post_calls[0]["model"] == "llava"


async def test_fetches_image_when_only_url(monkeypatch):
    content = json.dumps({"foods": [{"label": "salade", "confidence": 0.7}]})
    fake = _patch(monkeypatch, chat_content=content, image_bytes=b"\x89PNG")
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    detections = await provider.detect_foods("http://img/meal.jpg", None)

    assert detections[0].label == "salade"
    # L'image a été téléchargée puis encodée en base64 avant l'appel au modèle.
    import base64

    assert fake.post_calls[0]["messages"][0]["images"] == [
        base64.standard_b64encode(b"\x89PNG").decode("utf-8")
    ]


async def test_confidence_defaults_and_clamps(monkeypatch):
    content = json.dumps(
        {
            "foods": [
                {"label": "pain"},  # pas de confidence → défaut
                {"label": "beurre", "confidence": 1.5},  # > 1 → borné à 1.0
                {"label": "miel", "confidence": "abc"},  # invalide → défaut
                {"label": "carotte", "confidence": 0.3},  # < plancher → 0.6
            ]
        }
    )
    _patch(monkeypatch, chat_content=content)
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    detections = await provider.detect_foods(None, "b64")

    by_label = {d.label: d.confidence for d in detections}
    assert by_label["pain"] == 0.7
    assert by_label["beurre"] == 1.0
    assert by_label["miel"] == 0.7
    assert by_label["carotte"] == 0.6  # score bas relevé au plancher


async def test_skips_items_without_label(monkeypatch):
    content = json.dumps(
        {"foods": [{"confidence": 0.9}, "bad", {"label": "  ", "confidence": 0.5}]}
    )
    _patch(monkeypatch, chat_content=content)
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods(None, "b64") == []


# ---------------------------------------------------------------------------
# Robustesse / fallback
# ---------------------------------------------------------------------------


async def test_invalid_json_returns_empty(monkeypatch):
    _patch(monkeypatch, chat_content="pas du json")
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods(None, "b64") == []


async def test_unknown_shape_returns_empty(monkeypatch):
    _patch(monkeypatch, chat_content=json.dumps({"unexpected": True}))
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods(None, "b64") == []


async def test_post_error_returns_empty(monkeypatch):
    _patch(monkeypatch, raise_post=httpx.ConnectError("ollama down"))
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods(None, "b64") == []


async def test_image_fetch_error_returns_empty(monkeypatch):
    _patch(monkeypatch, raise_get=httpx.ConnectError("404"))
    provider = OllamaVisionProvider(endpoint="http://ollama:11434")

    assert await provider.detect_foods("http://img", None) == []
