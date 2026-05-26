"""Unit tests for domain imbalance detection (#88)."""

from app.contexts.nutrition.domain.models import (
    HealthProfile,
    ImbalanceStatus,
    Macros,
    MealStatus,
)
from app.contexts.nutrition.domain.services import NutritionImbalanceService


def _service() -> NutritionImbalanceService:
    return NutritionImbalanceService()


def test_balanced_meal_returns_equilibre():
    svc = _service()
    # A meal that matches exactly the per-meal targets (1/3 of daily)
    profile = HealthProfile(
        daily_calories_target=2100.0,
        proteins_target_g=90.0,
        carbs_target_g=270.0,
        fats_target_g=70.0,
        fibers_target_g=25.0,
    )
    macros = Macros(
        calories=700.0,   # 2100 / 3
        proteins_g=30.0,  # 90 / 3
        carbs_g=90.0,     # 270 / 3
        fats_g=23.3,      # 70 / 3
        fibers_g=8.3,     # 25 / 3
    )
    details, status = svc.detect_imbalances(macros, profile)

    assert status == MealStatus.EQUILIBRE
    for d in details:
        assert d.status == ImbalanceStatus.OK, f"{d.name} should be OK, got {d.status}"


def test_excess_calories_returns_desequilibre():
    svc = _service()
    macros = Macros(calories=1500.0, proteins_g=25.0, carbs_g=80.0, fats_g=23.0, fibers_g=8.0)
    # default profile → meal target ≈ 667 kcal → 1500 kcal is way above
    details, status = svc.detect_imbalances(macros)

    assert status == MealStatus.DESEQUILIBRE
    cal_detail = next(d for d in details if d.name == "calories")
    assert cal_detail.status == ImbalanceStatus.EXCES
    assert cal_detail.deviation_pct > 0


def test_protein_deficit_flags_correctly():
    svc = _service()
    # default daily proteins = 75 g → meal target = 25 g; we provide only 5 g
    macros = Macros(calories=667.0, proteins_g=5.0, carbs_g=83.0, fats_g=23.0, fibers_g=8.3)
    details, status = svc.detect_imbalances(macros)

    assert status == MealStatus.DESEQUILIBRE
    prot_detail = next(d for d in details if d.name == "proteins_g")
    assert prot_detail.status == ImbalanceStatus.DEFICIT
    assert prot_detail.deviation_pct < 0


def test_missing_profile_uses_goal_defaults():
    svc = _service()
    macros = Macros(calories=600.0, proteins_g=30.0, carbs_g=80.0, fats_g=20.0, fibers_g=8.0)
    details_default, _ = svc.detect_imbalances(macros, goal=None)
    details_goal, _ = svc.detect_imbalances(macros, goal="equilibre")

    # Both should use the same default equilibre profile
    assert len(details_default) == len(details_goal)


def test_details_include_all_nutrients():
    svc = _service()
    macros = Macros(calories=500.0, proteins_g=20.0, carbs_g=70.0, fats_g=15.0, fibers_g=5.0)
    details, _ = svc.detect_imbalances(macros)

    names = {d.name for d in details}
    assert names == {"calories", "proteins_g", "carbs_g", "fats_g", "fibers_g"}


def test_tolerance_boundary_is_ok():
    """Within ±15% should still be OK."""
    svc = _service()
    # default daily calories = 2000 → meal target ≈ 666.7 kcal
    # +14% ≈ 760 kcal → should still be OK
    macros = Macros(
        calories=760.0,
        proteins_g=25.0,
        carbs_g=83.0,
        fats_g=23.0,
        fibers_g=8.0,
    )
    details, _ = svc.detect_imbalances(macros)
    cal_detail = next(d for d in details if d.name == "calories")
    assert cal_detail.status == ImbalanceStatus.OK
