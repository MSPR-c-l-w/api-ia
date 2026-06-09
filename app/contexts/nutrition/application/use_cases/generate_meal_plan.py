from __future__ import annotations

import json
import logging

from app.contexts.nutrition.domain.ports import LlmProviderPort, NutritionLookupPort
from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.infrastructure.mongo_nutrition_recommendation_repository import (
    MongoNutritionRecommendationRepository,
)
from app.contexts.nutrition.presentation.schemas import (
    DailyMealPlan,
    MealPlanRequest,
    MealPlanResponse,
)

logger = logging.getLogger(__name__)


class GenerateMealPlanUseCase:
    """Generates a 7-day personalised meal plan.

    Priority: LLM (if configured) > MealComposer (from real food catalog) > static stub.
    """

    def __init__(
        self,
        llm_provider: LlmProviderPort | None = None,
        tdee_calculator: TdeeCalculator | None = None,
        nutrition_lookup: NutritionLookupPort | None = None,
        nutrition_repo: MongoNutritionRecommendationRepository | None = None,
    ) -> None:
        from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider

        self._llm = llm_provider or LlmProvider(endpoint=None, api_key=None)
        self._tdee = tdee_calculator or TdeeCalculator()
        self._nutrition_lookup = nutrition_lookup
        self._nutrition_repo = nutrition_repo or MongoNutritionRecommendationRepository()

    async def _persist(self, user_id: int | None, response: MealPlanResponse) -> None:
        if user_id is None:
            return
        try:
            await self._nutrition_repo.save(user_id, response.model_dump(by_alias=True))
        except Exception as exc:
            logger.warning("Impossible de persister la recommandation nutrition: %s", exc)

    async def execute(self, payload: MealPlanRequest) -> MealPlanResponse:
        constraints = {item.lower() for item in payload.dietary_constraints}
        allergies = {item.lower() for item in payload.allergies}
        daily_calories = self._resolve_calories(payload)

        # Try LLM-generated plan first (#89/#90)
        llm_days = await self._try_llm_plan(payload, daily_calories)
        if llm_days:
            result = MealPlanResponse(
                userGoal=payload.user_goal,
                days=llm_days,
                notes=[
                    "Plan généré par le modèle de langage.",
                    "Les préférences et contraintes déclarées sont prises en compte.",
                ],
                modelStatus="llm_active",
            )
            await self._persist(payload.user_id, result)
            return result

        # MealComposer fallback — uses the real Kaggle food catalog
        composer_days = await self._compose_plan(payload, constraints, allergies)
        if composer_days:
            scores = [d.get("score", 0) for d in composer_days]
            avg_score = round(sum(scores) / len(scores), 3) if scores else 0
            result = MealPlanResponse(
                userGoal=payload.user_goal,
                days=[
                    DailyMealPlan(
                        day=d["day"],
                        breakfast=d["breakfast"],
                        lunch=d["lunch"],
                        dinner=d["dinner"],
                        snack=d.get("snack"),
                        estimatedCalories=d["estimatedCalories"],
                    )
                    for d in composer_days
                ],
                notes=[
                    f"Plan composé à partir du catalogue de {await self._catalog_size()} aliments validés.",
                    f"Score moyen d'équilibre nutritionnel : {avg_score:.3f}/1.0",
                    "Les contraintes et allergies déclarées sont appliquées.",
                ],
                modelStatus="composer_active",
            )
            await self._persist(payload.user_id, result)
            return result

        # Static stub fallback (last resort)
        result = MealPlanResponse(
            userGoal=payload.user_goal,
            days=self._static_plan(constraints, allergies, daily_calories),
            notes=[
                "Plan généré en mode stub local.",
                "Les préférences et contraintes déclarées sont prises en compte.",
            ],
            modelStatus="stub_ready_for_llm",
        )
        await self._persist(payload.user_id, result)
        return result

    def _resolve_calories(self, payload: MealPlanRequest) -> int:
        """Return daily caloric target: TDEE (if biometrics) > explicit target > goal default."""
        return int(
            self._tdee.resolve_health_profile(
                goal=payload.user_goal,
                weight_kg=payload.weight_kg,
                height_cm=payload.height_cm,
                age_years=payload.age_years,
                gender=payload.gender,
                physical_activity_level=payload.physical_activity_level
                or "moderately_active",
                daily_calories_target=payload.daily_calories_target,
            ).daily_calories_target
        )

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

    async def _compose_plan(
        self,
        payload: MealPlanRequest,
        constraints: set[str],
        allergies: set[str],
    ) -> list[dict] | None:
        """Use MealComposerService to build a 7-day plan from the real food catalog."""
        from app.contexts.nutrition.domain.meal_composer import MealComposerService

        lookup = self._nutrition_lookup
        if lookup is None:
            return None

        try:
            catalog = await lookup.get_catalog()
        except AttributeError:
            return None

        if not catalog:
            return None

        # Resolve health profile
        profile = self._tdee.resolve_health_profile(
            goal=payload.user_goal,
            weight_kg=payload.weight_kg,
            height_cm=payload.height_cm,
            age_years=payload.age_years,
            gender=payload.gender,
            physical_activity_level=payload.physical_activity_level
            or "moderately_active",
            daily_calories_target=payload.daily_calories_target,
        )

        try:
            composer = MealComposerService(catalog)
            return composer.compose_week(profile, constraints, allergies)
        except Exception as exc:
            logger.warning("MealComposer failed: %s", exc)
            return None

    async def _catalog_size(self) -> int:
        """Return number of items in the food catalog."""
        if self._nutrition_lookup is None:
            return 0
        try:
            return len(await self._nutrition_lookup.get_catalog())
        except AttributeError:
            return 0

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
