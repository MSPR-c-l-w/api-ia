"""LLM provider with static fallback for personalised nutrition suggestions (#89).

Supports Ollama-compatible endpoints.
Falls back to curated static suggestions when the LLM is unavailable.
"""

from __future__ import annotations

import json
import logging

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static suggestion banks
# ---------------------------------------------------------------------------

_GOAL_SUGGESTIONS: dict[str, list[str]] = {
    "perte_de_poids": [
        "Réduisez les glucides simples au profit des fibres et des protéines.",
        "Privilégiez des repas rassasiants à faible densité calorique.",
        "Hydratez-vous suffisamment (1,5 à 2 L d'eau par jour).",
        "Fractionnez vos repas pour éviter les fringales.",
    ],
    "prise_de_masse": [
        "Augmentez l'apport en protéines pour soutenir la synthèse musculaire.",
        "Consommez des glucides complexes avant et après l'entraînement.",
        "Assurez un surplus calorique modéré (300-500 kcal/jour).",
        "N'oubliez pas les graisses saines (avocat, noix, poisson gras).",
    ],
    "equilibre": [
        "Variez les sources de protéines (légumineuses, poisson, œufs).",
        "Privilégiez les céréales complètes pour un indice glycémique bas.",
        "Incluez des légumes à chaque repas pour couvrir vos besoins en micronutriments.",
        "Limitez les aliments ultra-transformés.",
    ],
}

_IMBALANCE_SUGGESTIONS: dict[str, str] = {
    "calories_EXCES": "Réduisez les portions pour respecter votre objectif calorique.",
    "calories_DEFICIT": "Augmentez légèrement les portions ou ajoutez une collation nutritive.",
    "proteins_g_DEFICIT": "Ajoutez une source de protéines (œuf, légumineuse, poisson).",
    "proteins_g_EXCES": "Équilibrez les protéines avec plus de glucides complexes.",
    "carbs_g_EXCES": "Réduisez les glucides simples (sucres, pain blanc, sodas).",
    "carbs_g_DEFICIT": "Incluez des féculents complets pour l'énergie durable.",
    "fats_g_EXCES": "Limitez les matières grasses ajoutées ; privilégiez les graisses insaturées.",
    "fats_g_DEFICIT": "Ajoutez une source de bons lipides (avocat, huile d'olive, noix).",
    "fibers_g_DEFICIT": "Ajoutez des légumes, fruits ou céréales complètes pour les fibres.",
    "fibers_g_EXCES": "Une consommation élevée de fibres est généralement bénéfique ; restez bien hydraté.",
}


class LlmProvider:
    """HTTP adapter for Ollama NLP with static fallback."""

    def __init__(
        self,
        endpoint: str | None,
        api_key: str | None,
        timeout_seconds: int = 30,
        max_suggestions: int = 5,
    ) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout_seconds
        self._max = max_suggestions

    async def generate_suggestions(
        self,
        goal: str,
        imbalance_tokens: list[str],
        dietary_constraints: list[str] | None = None,
    ) -> list[str]:
        """Return a list of French nutrition tips (max *max_suggestions* items)."""
        if self._endpoint:
            result = await self._call_llm(goal, imbalance_tokens, dietary_constraints)
            if result:
                logger.info("LLM suggestions generated (provider=remote goal=%s)", goal)
                return result[: self._max]
        logger.info("Using static suggestions fallback (goal=%s)", goal)
        return self._static_suggestions(goal, imbalance_tokens)

    async def generate_meal_plan_text(
        self,
        goal: str,
        dietary_constraints: list[str],
        allergies: list[str],
        daily_calories: int,
    ) -> str | None:
        """Ask LLM for a raw 7-day meal plan JSON string. Returns None on failure."""
        if not self._endpoint:
            return None

        allergies_text = f"Allergies à exclure : {', '.join(allergies)}." if allergies else ""
        constraints_text = (
            f"Contraintes alimentaires : {', '.join(dietary_constraints)}."
            if dietary_constraints
            else ""
        )

        prompt = (
            "Tu es un nutritionniste expert. Réponds uniquement en français et en JSON.\n"
            f"Objectif : {goal}. Calories quotidiennes : {daily_calories} kcal.\n"
            f"{constraints_text} {allergies_text}\n"
            "Génère un plan repas pour 7 jours (petit-déjeuner, déjeuner, dîner, collation). "
            'Format JSON : {"days": [{"day": 1, "breakfast": "...", "lunch": "...", '
            '"dinner": "...", "snack": "...", "estimatedCalories": N}, ...]}'
        )

        payload = {"model": "mistral", "prompt": prompt, "stream": False}
        return await self._post_json(payload)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _call_llm(
        self,
        goal: str,
        imbalance_tokens: list[str],
        dietary_constraints: list[str] | None,
    ) -> list[str] | None:
        constraints_text = (
            f"Contraintes alimentaires : {', '.join(dietary_constraints)}."
            if dietary_constraints
            else ""
        )
        imbalances_text = (
            f"Déséquilibres détectés : {', '.join(imbalance_tokens)}."
            if imbalance_tokens
            else "Repas globalement équilibré."
        )
        prompt = (
            "Tu es un nutritionniste expert. Réponds uniquement en français.\n"
            f"Objectif de l'utilisateur : {goal}.\n"
            f"{imbalances_text}\n{constraints_text}\n"
            "Donne exactement 3 à 5 conseils nutritionnels courts et personnalisés "
            'au format JSON : {"suggestions": ["...", "..."]}'
        )

        raw = await self._post_json({"model": "mistral", "prompt": prompt, "stream": False})
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            text = data.get("response") or data.get("content") or ""
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(text[start:end])
                suggestions = parsed.get("suggestions", [])
                if isinstance(suggestions, list) and suggestions:
                    return [str(s) for s in suggestions]
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None

    async def _post_json(self, payload: dict) -> str | None:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    self._endpoint,
                    content=json.dumps(payload),
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.text
        except httpx.HTTPError as exc:
            logger.warning("LLM endpoint unavailable (%s)", exc)
            return None

    def _static_suggestions(self, goal: str, imbalance_tokens: list[str]) -> list[str]:
        suggestions: list[str] = []

        for token in imbalance_tokens:
            tip = _IMBALANCE_SUGGESTIONS.get(token)
            if tip and tip not in suggestions:
                suggestions.append(tip)

        goal_key = goal if goal in _GOAL_SUGGESTIONS else "equilibre"
        for tip in _GOAL_SUGGESTIONS[goal_key]:
            if tip not in suggestions and len(suggestions) < self._max:
                suggestions.append(tip)

        return suggestions[: self._max]
