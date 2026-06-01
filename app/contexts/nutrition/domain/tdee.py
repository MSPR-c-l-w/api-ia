"""TDEE (Total Daily Energy Expenditure) calculator using the Mifflin-St Jeor BMR formula.

Computes personalised daily caloric and macro targets from user biometrics,
replacing the generic goal-based static profiles when biometric data is available.
"""

from __future__ import annotations

from app.contexts.nutrition.domain.models import GOAL_PROFILES, HealthProfile

# Activity multipliers (PAL — Physical Activity Level)
_ACTIVITY_MULTIPLIERS: dict[str, float] = {
    "sedentary": 1.2,  # desk job, no exercise
    "lightly_active": 1.375,  # light exercise 1–3 days/week
    "moderately_active": 1.55,  # moderate exercise 3–5 days/week
    "very_active": 1.725,  # hard exercise 6–7 days/week
    "extra_active": 1.9,  # physical job + hard exercise / athlete
}

# Goal caloric adjustments (kcal/day relative to TDEE)
_GOAL_ADJUSTMENTS: dict[str, float] = {
    "perte_de_poids": -400.0,  # moderate deficit
    "prise_de_masse": +350.0,  # lean bulk surplus
    "equilibre": 0.0,
}

# Protein targets by goal (g per kg of body weight)
_PROTEIN_G_PER_KG: dict[str, float] = {
    "perte_de_poids": 1.8,
    "prise_de_masse": 2.2,
    "equilibre": 1.4,
}


class TdeeCalculator:
    """Compute personalised nutritional targets from biometrics."""

    def resolve_health_profile(
        self,
        goal: str,
        weight_kg: float | None = None,
        height_cm: float | None = None,
        age_years: int | None = None,
        gender: str | None = None,
        physical_activity_level: str = "moderately_active",
        daily_calories_target: float | None = None,
    ) -> HealthProfile:
        """Return a HealthProfile using the priority chain:
        1. Explicit daily_calories_target (overrides everything else).
        2. Full biometrics → personalised TDEE.
        3. Goal-based static default.
        """
        if daily_calories_target:
            base = GOAL_PROFILES.get(goal) or HealthProfile()
            return base.model_copy(
                update={"daily_calories_target": float(daily_calories_target)}
            )

        if all(v is not None for v in (weight_kg, height_cm, age_years, gender)):
            return self.compute(
                weight_kg=weight_kg,
                height_cm=height_cm,
                age_years=age_years,
                gender=gender,
                physical_activity_level=physical_activity_level,
                goal=goal,
            )

        return GOAL_PROFILES.get(goal) or HealthProfile()

    def compute(
        self,
        weight_kg: float,
        height_cm: float,
        age_years: int,
        gender: str,  # "male" | "female"
        physical_activity_level: str = "moderately_active",
        goal: str = "equilibre",
    ) -> HealthProfile:
        """Return a HealthProfile with targets derived from biometrics.

        Uses Mifflin-St Jeor for BMR, then multiplies by PAL factor.
        Macro split: 30% protein / 45% carbs / 25% fat (adjusted by goal).
        """
        # 1. BMR (Mifflin-St Jeor)
        if gender.lower() in ("female", "femme", "f"):
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age_years - 161
        else:
            bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age_years + 5

        # 2. TDEE
        pal = _ACTIVITY_MULTIPLIERS.get(physical_activity_level, 1.55)
        tdee = bmr * pal

        # 3. Goal adjustment
        adjustment = _GOAL_ADJUSTMENTS.get(goal, 0.0)
        daily_calories = max(1200.0, tdee + adjustment)

        # 4. Macros
        protein_g = round(_PROTEIN_G_PER_KG.get(goal, 1.4) * weight_kg, 1)
        protein_kcal = protein_g * 4

        # Remaining calories split 64% carbs / 36% fat
        remaining = max(0.0, daily_calories - protein_kcal)
        carbs_g = round((remaining * 0.64) / 4, 1)
        fats_g = round((remaining * 0.36) / 9, 1)

        fibers_g = 30.0 if goal == "perte_de_poids" else 25.0

        return HealthProfile(
            daily_calories_target=round(daily_calories),
            proteins_target_g=protein_g,
            carbs_target_g=carbs_g,
            fats_target_g=fats_g,
            fibers_target_g=fibers_g,
        )
