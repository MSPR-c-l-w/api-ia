"""Tests for TDEE calculator and biometric integration in use cases (#88 extended)."""

import asyncio

from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.application.use_cases.generate_meal_plan import GenerateMealPlanUseCase
from app.contexts.nutrition.domain.models import VisionDetection
from app.contexts.nutrition.presentation.schemas import (
    NutritionAnalysisRequest,
    MealPlanRequest,
)


# ---------------------------------------------------------------------------
# TdeeCalculator unit tests
# ---------------------------------------------------------------------------


def test_tdee_male_moderately_active():
    calc = TdeeCalculator()
    profile = calc.compute(
        weight_kg=80, height_cm=180, age_years=30,
        gender="male", physical_activity_level="moderately_active", goal="equilibre"
    )
    # BMR = 10*80 + 6.25*180 - 5*30 + 5 = 800+1125-150+5 = 1780 kcal
    # TDEE = 1780 * 1.55 ≈ 2759 kcal
    assert 2600 < profile.daily_calories_target < 2900
    assert profile.proteins_target_g > 0
    assert profile.carbs_target_g > 0
    assert profile.fats_target_g > 0


def test_tdee_female_sedentary_weight_loss():
    calc = TdeeCalculator()
    profile = calc.compute(
        weight_kg=65, height_cm=162, age_years=45,
        gender="female", physical_activity_level="sedentary", goal="perte_de_poids"
    )
    # BMR ≈ 10*65 + 6.25*162 - 5*45 - 161 = 650+1012.5-225-161 = 1276.5
    # TDEE = 1276.5 * 1.2 ≈ 1532 kcal
    # With -400 adjustment ≈ 1132 kcal
    assert 1000 < profile.daily_calories_target < 1400
    assert profile.proteins_target_g == round(1.8 * 65, 1)  # 117 g


def test_tdee_bulk_has_higher_calories_than_cut():
    calc = TdeeCalculator()
    base = dict(weight_kg=75, height_cm=175, age_years=25, gender="male",
                physical_activity_level="moderately_active")
    bulk = calc.compute(**base, goal="prise_de_masse")
    cut = calc.compute(**base, goal="perte_de_poids")
    assert bulk.daily_calories_target > cut.daily_calories_target


def test_tdee_minimum_calories_floor():
    """Very light person should never go below 1200 kcal."""
    calc = TdeeCalculator()
    profile = calc.compute(
        weight_kg=40, height_cm=150, age_years=80,
        gender="female", physical_activity_level="sedentary", goal="perte_de_poids"
    )
    assert profile.daily_calories_target >= 1200


def test_tdee_unknown_activity_defaults_to_moderate():
    calc = TdeeCalculator()
    profile_unknown = calc.compute(
        weight_kg=70, height_cm=170, age_years=30,
        gender="male", physical_activity_level="unknown_level", goal="equilibre"
    )
    profile_moderate = calc.compute(
        weight_kg=70, height_cm=170, age_years=30,
        gender="male", physical_activity_level="moderately_active", goal="equilibre"
    )
    assert profile_unknown.daily_calories_target == profile_moderate.daily_calories_target


# ---------------------------------------------------------------------------
# Integration: biometric fields used in AnalyzeMealUseCase
# ---------------------------------------------------------------------------


class EmptyProvider:
    async def detect_foods(self, image_url, image_base64):
        return []


class FoodProvider:
    async def detect_foods(self, image_url, image_base64):
        return [VisionDetection(label="salade", confidence=0.91)]


def test_analyze_with_biometrics_uses_personalised_targets():
    """When biometrics are provided, targets should differ from generic defaults."""
    use_case = AnalyzeMealUseCase(vision_providers=[FoodProvider()])
    payload_bio = NutritionAnalysisRequest(
        imageUrl="https://example.com/meal.jpg",
        userGoal="perte_de_poids",
        weightKg=90,
        heightCm=185,
        ageYears=35,
        gender="male",
        physicalActivityLevel="very_active",
    )
    payload_no_bio = NutritionAnalysisRequest(
        imageUrl="https://example.com/meal.jpg",
        userGoal="perte_de_poids",
    )

    result_bio = asyncio.run(use_case.execute(payload_bio))
    result_no_bio = asyncio.run(use_case.execute(payload_no_bio))

    # Targets should differ: a 90kg very active male has much higher TDEE than 1700 kcal default
    bio_targets = {d.name: d.target for d in result_bio.nutrient_details}
    no_bio_targets = {d.name: d.target for d in result_no_bio.nutrient_details}
    assert bio_targets["calories"] != no_bio_targets["calories"]


def test_analyze_daily_calories_target_overrides_tdee():
    """Explicit dailyCaloriesTarget overrides TDEE calculation."""
    use_case = AnalyzeMealUseCase(vision_providers=[EmptyProvider()])
    payload = NutritionAnalysisRequest(
        imageUrl="https://example.com/meal.jpg",
        userGoal="equilibre",
        weightKg=70,
        heightCm=170,
        ageYears=30,
        gender="male",
        physicalActivityLevel="moderately_active",
        dailyCaloriesTarget=2000,
    )
    result = asyncio.run(use_case.execute(payload))
    cal_detail = next(d for d in result.nutrient_details if d.name == "calories")
    # daily target = 2000, meal target = 2000/3 ≈ 666.7
    assert abs(cal_detail.target - 2000 / 3) < 5


# ---------------------------------------------------------------------------
# Integration: biometric fields used in GenerateMealPlanUseCase
# ---------------------------------------------------------------------------


def test_meal_plan_with_biometrics_uses_tdee_calories():
    """A 90kg very active male should get much more than the default 1900/2300 kcal."""
    use_case = GenerateMealPlanUseCase()
    payload = MealPlanRequest(
        userGoal="prise_de_masse",
        weightKg=90,
        heightCm=185,
        ageYears=25,
        gender="male",
        physicalActivityLevel="very_active",
    )
    result = asyncio.run(use_case.execute(payload))
    # Default for prise_de_masse = 2300; TDEE for 90kg/185cm/25/male/very_active ≈ 3800+350=4150
    assert result.days[0].estimated_calories > 2500


def test_meal_plan_explicit_calories_takes_priority_over_tdee():
    use_case = GenerateMealPlanUseCase()
    payload = MealPlanRequest(
        userGoal="equilibre",
        weightKg=80,
        heightCm=175,
        ageYears=30,
        gender="male",
        physicalActivityLevel="very_active",
        dailyCaloriesTarget=2100,
    )
    result = asyncio.run(use_case.execute(payload))
    assert result.days[0].estimated_calories == 2100
