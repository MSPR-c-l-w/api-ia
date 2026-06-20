"""Tests unitaires de LlmProvider (suggestions nutrition + plan repas).

Le client httpx.AsyncClient est remplacé par un faux client asynchrone pour
éviter tout appel réseau.
"""

import json

import httpx

from app.contexts.nutrition.infrastructure import llm_provider
from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider


class _FakeAsyncClient:
    """Faux httpx.AsyncClient pilotable par une réponse ou une exception."""

    def __init__(self, *, text: str | None = None, raise_exc: Exception | None = None):
        self._text = text
        self._raise = raise_exc
        self.last_content: bytes | None = None

    def __call__(self, *args, **kwargs):  # instancié comme httpx.AsyncClient(...)
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, content=None, headers=None):
        self.last_content = content
        if self._raise is not None:
            raise self._raise
        return httpx.Response(200, text=self._text, request=httpx.Request("POST", url))


def _patch_client(monkeypatch, **kwargs) -> _FakeAsyncClient:
    fake_client = _FakeAsyncClient(**kwargs)
    monkeypatch.setattr(llm_provider.httpx, "AsyncClient", fake_client)
    return fake_client


# ---------------------------------------------------------------------------
# Fallback statique (pas d'endpoint)
# ---------------------------------------------------------------------------


async def test_static_suggestions_without_endpoint():
    provider = LlmProvider(endpoint=None, api_key=None)

    result = await provider.generate_suggestions("perte_de_poids", [])

    assert len(result) > 0
    assert all(isinstance(s, str) for s in result)


async def test_static_suggestions_prioritise_imbalances():
    provider = LlmProvider(endpoint=None, api_key=None, max_suggestions=5)

    result = await provider.generate_suggestions(
        "equilibre", ["proteins_g_DEFICIT", "calories_EXCES"]
    )

    assert any("protéines" in s.lower() for s in result)


async def test_static_suggestions_respect_max():
    provider = LlmProvider(endpoint=None, api_key=None, max_suggestions=2)

    result = await provider.generate_suggestions("prise_de_masse", [])

    assert len(result) <= 2


async def test_unknown_goal_falls_back_to_equilibre():
    provider = LlmProvider(endpoint=None, api_key=None)

    result = await provider.generate_suggestions("objectif_inconnu", [])

    assert len(result) > 0


async def test_meal_plan_text_none_without_endpoint():
    provider = LlmProvider(endpoint=None, api_key=None)

    assert await provider.generate_meal_plan_text("equilibre", [], [], 2000) is None


# ---------------------------------------------------------------------------
# Chemin LLM distant
# ---------------------------------------------------------------------------


async def test_remote_suggestions_parsed(monkeypatch):
    inner = json.dumps({"suggestions": ["Mange des légumes.", "Bois de l'eau."]})
    body = json.dumps({"response": f"Voici mes conseils : {inner}"})
    _patch_client(monkeypatch, text=body)
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key="k")

    result = await provider.generate_suggestions("equilibre", [])

    assert result == ["Mange des légumes.", "Bois de l'eau."]


async def test_remote_falls_back_when_http_error(monkeypatch):
    _patch_client(monkeypatch, raise_exc=httpx.ConnectError("down"))
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key=None)

    result = await provider.generate_suggestions("perte_de_poids", [])

    # Le provider retombe sur les suggestions statiques.
    assert len(result) > 0


async def test_remote_falls_back_when_invalid_json(monkeypatch):
    _patch_client(monkeypatch, text="pas du json")
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key=None)

    result = await provider.generate_suggestions("equilibre", [])

    assert len(result) > 0


async def test_meal_plan_text_returns_raw_body(monkeypatch):
    body = json.dumps({"response": '{"days": []}'})
    _patch_client(monkeypatch, text=body)
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key="k")

    result = await provider.generate_meal_plan_text(
        "equilibre", ["vegetarien"], ["arachides"], 2100
    )

    assert result == body


async def test_meal_plan_text_includes_budget_in_prompt(monkeypatch):
    fake_client = _patch_client(monkeypatch, text=json.dumps({"response": "{}"}))
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key="k")

    await provider.generate_meal_plan_text(
        "equilibre",
        [],
        [],
        2100,
        budget=150.0,
    )

    assert "150" in fake_client.last_content
    assert "budget" in fake_client.last_content.lower()


async def test_meal_plan_text_omits_budget_text_when_none(monkeypatch):
    fake_client = _patch_client(monkeypatch, text=json.dumps({"response": "{}"}))
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key="k")

    await provider.generate_meal_plan_text("equilibre", [], [], 2100)

    assert "budget" not in fake_client.last_content.lower()


async def test_meal_plan_text_none_on_http_error(monkeypatch):
    _patch_client(monkeypatch, raise_exc=httpx.ConnectError("down"))
    provider = LlmProvider(endpoint="http://ollama:11434/api/generate", api_key=None)

    assert await provider.generate_meal_plan_text("equilibre", [], [], 2000) is None
