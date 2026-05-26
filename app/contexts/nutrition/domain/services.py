from __future__ import annotations

from app.contexts.nutrition.domain.models import (
    GOAL_PROFILES,
    HealthProfile,
    ImbalanceStatus,
    Macros,
    MealStatus,
    NutrientDetail,
)

# A meal is assumed to represent ~1/3 of daily intake
_MEAL_FRACTION = 1 / 3
# ±N% is considered acceptable (no imbalance flagged)
_TOLERANCE_PCT = 15.0


class NutritionImbalanceService:
    """
    Compares macros from a single meal against per-meal targets derived from a
    daily health profile and classifies each nutrient as OK / EXCES / DEFICIT.
    """

    def detect_imbalances(
        self,
        macros: Macros,
        health_profile: HealthProfile | None = None,
        goal: str | None = None,
    ) -> tuple[list[NutrientDetail], MealStatus]:
        """Return (nutrient_details, meal_status).

        If *health_profile* is None, a default profile is inferred from *goal*.
        """
        if health_profile is None:
            health_profile = GOAL_PROFILES.get(goal or "equilibre") or HealthProfile()

        meal_targets = {
            "calories": health_profile.daily_calories_target * _MEAL_FRACTION,
            "proteins_g": health_profile.proteins_target_g * _MEAL_FRACTION,
            "carbs_g": health_profile.carbs_target_g * _MEAL_FRACTION,
            "fats_g": health_profile.fats_target_g * _MEAL_FRACTION,
            "fibers_g": health_profile.fibers_target_g * _MEAL_FRACTION,
        }

        actuals = {
            "calories": macros.calories,
            "proteins_g": macros.proteins_g,
            "carbs_g": macros.carbs_g,
            "fats_g": macros.fats_g,
            "fibers_g": macros.fibers_g,
        }

        units = {
            "calories": "kcal",
            "proteins_g": "g",
            "carbs_g": "g",
            "fats_g": "g",
            "fibers_g": "g",
        }

        details: list[NutrientDetail] = []
        has_imbalance = False

        for name, target in meal_targets.items():
            actual = actuals[name]
            deviation_pct = ((actual - target) / target * 100) if target > 0 else 0.0

            if abs(deviation_pct) <= _TOLERANCE_PCT:
                status = ImbalanceStatus.OK
            elif deviation_pct > 0:
                status = ImbalanceStatus.EXCES
                has_imbalance = True
            else:
                status = ImbalanceStatus.DEFICIT
                has_imbalance = True

            details.append(
                NutrientDetail(
                    name=name,
                    actual=round(actual, 1),
                    target=round(target, 1),
                    unit=units[name],
                    status=status,
                    deviation_pct=round(deviation_pct, 1),
                )
            )

        meal_status = MealStatus.DESEQUILIBRE if has_imbalance else MealStatus.EQUILIBRE
        return details, meal_status
