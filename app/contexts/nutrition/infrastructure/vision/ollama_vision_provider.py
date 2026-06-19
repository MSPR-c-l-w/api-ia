"""VisionProviderPort servi par un modèle de vision Ollama local (gratuit).

Détecte les aliments d'un plat via un modèle multimodal hébergé localement par
Ollama (llava, moondream, qwen2.5-vl…). Aucun coût au token : tout tourne en
local. Le modèle renvoie une liste d'aliments en JSON, ensuite résolus en macros
par le catalogue MongoDB (``MongoNutritionLookupService``).

Pattern fail-open : si le endpoint est absent ou l'appel échoue, on renvoie une
liste vide et le use case retombe sur le provider suivant puis sur le stub —
aucune régression.
"""

from __future__ import annotations

import base64
import json
import logging

import httpx

from app.contexts.nutrition.domain.models import VisionDetection

logger = logging.getLogger(__name__)

_PROMPT = (
    "Identifie chaque aliment réellement présent dans ce plat. "
    'Réponds UNIQUEMENT en JSON : {"foods":[{"label":"...","confidence":0.0}]}. '
    "Utilise des noms simples en français, au singulier. N'invente aucun aliment."
)
_DEFAULT_CONFIDENCE = 0.7


class OllamaVisionProvider:
    """Détection d'aliments via un modèle de vision Ollama local."""

    name = "ollama_vision"

    def __init__(
        self,
        endpoint: str | None,
        model: str = "llava",
        timeout_seconds: int = 60,
    ) -> None:
        self._endpoint = (endpoint or "").rstrip("/")
        self._model = model
        self._timeout = timeout_seconds

    async def detect_foods(
        self,
        image_url: str | None,
        image_base64: str | None,
    ) -> list[VisionDetection]:
        if not self._endpoint:
            return []
        try:
            image = image_base64 or await self._fetch_base64(image_url)
            if not image:
                return []

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._endpoint}/api/chat",
                    json={
                        "model": self._model,
                        "stream": False,
                        "format": "json",
                        "messages": [
                            {
                                "role": "user",
                                "content": _PROMPT,
                                "images": [image],
                            }
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")

            return self._parse(content)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OllamaVisionProvider: détection impossible (%s) — fallback.", exc
            )
            return []

    # ------------------------------------------------------------------
    # Internes
    # ------------------------------------------------------------------

    def _parse(self, content: str) -> list[VisionDetection]:
        try:
            payload = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return []

        foods = payload.get("foods") if isinstance(payload, dict) else None
        if not isinstance(foods, list):
            return []

        detections: list[VisionDetection] = []
        for food in foods:
            if not isinstance(food, dict):
                continue
            label = str(food.get("label", "")).strip()
            if not label:
                continue
            try:
                confidence = float(food.get("confidence", _DEFAULT_CONFIDENCE))
            except (TypeError, ValueError):
                confidence = _DEFAULT_CONFIDENCE
            confidence = min(max(confidence, 0.0), 1.0)
            detections.append(VisionDetection(label=label, confidence=confidence))
        return detections

    async def _fetch_base64(self, image_url: str | None) -> str | None:
        if not image_url:
            return None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
        return base64.standard_b64encode(resp.content).decode("utf-8")
