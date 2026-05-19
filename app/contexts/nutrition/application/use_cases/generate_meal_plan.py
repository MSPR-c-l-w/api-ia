from __future__ import annotations

import json
import logging

from app.contexts.nutrition.domain.ports import LlmProviderPort
from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.presentation.schemas import (
    DailyMealPlan,
    MealPlanRequest,
    MealPlanResponse,
)

logger = logging.getLogger(__name__)


class GenerateMealPlanUseCase:
    """Generates a 7-day personalised meal plan via LLM with a local stub fallback."""

    def __init__(
        self,
        llm_provider: LlmProviderPort | None = None,
        tdee_calculator: TdeeCalculator | None = None,
    ) -> None:
        from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider

        self._llm = llm_provider or LlmProvider(endpoint=None, api_key=None)
        self._tdee = tdee_calculator or TdeeCalculator()

    async def execute(self, payload: MealPlanRequest) -> MealPlanResponse:
        constraints = {item.lower() for item in payload.dietary_constraints}
        allergies = {item.lower() for item in payload.allergies}
        daily_calories = self._resolve_calories(payload)

        # Try LLM-generated plan first (#89/#90)
        llm_days = await self._try_llm_plan(payload, daily_calories)
        if llm_days:
            return MealPlanResponse(
                userGoal=payload.user_goal,
                days=llm_days,
                notes=[
                    "Plan généré par le modèle de langage.",
                    "Les préférences et contraintes déclarées sont prises en compte.",
                ],
                modelStatus="llm_active",
            )

        # Static fallback
        return MealPlanResponse(
            userGoal=payload.user_goal,
            days=self._static_plan(constraints, allergies, daily_calories),
            notes=[
                "Plan généré en mode stub local.",
                "Les préférences et contraintes déclarées sont prises en compte.",
            ],
            modelStatus="stub_ready_for_llm",
        )

    def _resolve_calories(self, payload: MealPlanRequest) -> int:
        """Return daily caloric target: TDEE (if biometrics) > explicit target > goal default."""
        if payload.daily_calories_target:
            return payload.daily_calories_target

        has_biometrics = (
            payload.weight_kg is not None
            and payload.height_cm is not None
            and payload.age_years is not None
            and payload.gender is not None
        )
        if has_biometrics:
            profile = self._tdee.compute(
                weight_kg=payload.weight_kg,
                height_cm=payload.height_cm,
                age_years=payload.age_years,
                gender=payload.gender,
                physical_activity_level=payload.physical_activity_level or "moderately_active",
                goal=payload.user_goal,
            )
            return int(profile.daily_calories_target)

        return 1900 if payload.user_goal == "perte_de_poids" else 2300

    async def _try_llm_plan(
        self, payload: MealPlanRequest, daily_calories: int
    ) -> list[DailyMealPlan] | None:
        raw = await self._llm.generate_meal_plan_text(
            goal=payload.user_goal,
            dietary_constraints=payload.dietary_constraints,
            allergies=payload.allergies,
            daily_calories=daily_calories,
        )
        if raw is None:
            return None
        try:
            data = json.loads(raw)
            # Ollama wraps response in {"response": "..."}
            if "response" in data:
                inner = data["response"]
                start = inner.find("{")
                end = inner.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(inner[start:end])
            days_raw = data.get("days", [])
            if not isinstance(days_raw, list) or len(days_raw) != 7:
                return None
            return [
                DailyMealPlan(
                    day=int(d["day"]),
                    breakfast=str(d.get("breakfast", "")),
                    lunch=str(d.get("lunch", "")),
                    dinner=str(d.get("dinner", "")),
                    snack=d.get("snack"),
                    estimatedCalories=int(d.get("estimatedCalories", daily_calories)),
                )
                for d in days_raw
            ]
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            logger.warning("Failed to parse LLM meal plan: %s", exc)
            return None

    @staticmethod
    def _static_plan(
        constraints: set[str],
        allergies: set[str],
        daily_calories: int,
    ) -> list[DailyMealPlan]:
        protein_main = "tofu mariné" if "vegetarien" in constraints else "poulet grillé"
        fish_main = "tempeh laqué" if "vegetarien" in constraints else "saumon"
        snack = "Amandes" if "arachide" not in allergies else "Yaourt nature"

        return [
            DailyMealPlan(
                day=day,
                breakfast="Skyr, fruits rouges et flocons d'avoine",
                lunch=f"Bowl quinoa, légumes rôtis et {protein_main}",
                dinner=f"{fish_main}, légumes verts et patate douce",
                snack=snack,
                estimatedCalories=daily_calories,
            )
            for day in range(1, 8)
        ]


