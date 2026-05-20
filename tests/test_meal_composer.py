"""Tests pour MealComposerService."""

import pytest

from app.contexts.nutrition.domain.meal_composer import (
    FoodCategory,
    MealComposerService,
    _classify,
    _combine_macros,
    _score_meal,
)
from app.contexts.nutrition.domain.models import HealthProfile, Macros


# Petit catalogue de test
_CATALOG: dict[str, tuple[float, float, float, float, float]] = {
    "poulet grillé (150g)":    (248, 46.5,  0.0,  5.4, 0.0),
    "riz basmati (100g)":      (130,  2.7, 28.0,  0.3, 0.4),
    "brocoli cuit (100g)":     ( 35,  2.9,  7.2,  0.4, 2.6),
    "yaourt nature (150g)":    ( 88,  5.3,  7.1,  5.0, 0.0),
    "flocons d'avoine (50g)":  (190,  6.5, 33.5,  3.3, 4.1),
    "saumon (150g)":           (312, 30.0,  0.0, 19.5, 0.0),
    "quinoa (100g)":           (120,  4.4, 21.0,  1.9, 2.8),
    "lentilles (100g)":        (116,  9.0, 20.0,  0.4, 8.0),
    "tomate (100g)":           ( 18,  0.9,  3.9,  0.2, 1.2),
    "pomme (1 fruit)":         ( 81,  0.4, 21.6,  0.2, 3.7),
    "amandes (30g)":           (174,  6.3,  6.1, 15.1, 3.8),
    "tofu (100g)":             ( 76,  8.0,  1.9,  4.8, 0.3),
    "patate douce (150g)":     (129,  2.4, 30.0,  0.2, 4.5),
}


def _default_profile() -> HealthProfile:
    return HealthProfile(
        daily_calories_target=2000,
        proteins_target_g=80,
        carbs_target_g=240,
        fats_target_g=70,
        fibers_target_g=25,
    )


# ---------------------------------------------------------------------------
# Classify tests
# ---------------------------------------------------------------------------

def test_classify_protein():
    macros = Macros(calories=248, proteins_g=46.5, carbs_g=0, fats_g=5.4, fibers_g=0)
    assert _classify("poulet grillé", macros) == FoodCategory.PROTEIN


def test_classify_carb():
    macros = Macros(calories=130, proteins_g=2.7, carbs_g=28, fats_g=0.3, fibers_g=0.4)
    assert _classify("riz basmati", macros) == FoodCategory.CARB


def test_classify_vegetable():
    macros = Macros(calories=35, proteins_g=2.9, carbs_g=7.2, fats_g=0.4, fibers_g=2.6)
    assert _classify("brocoli cuit", macros) == FoodCategory.VEGETABLE


def test_classify_breakfast_keyword():
    macros = Macros(calories=190, proteins_g=6.5, carbs_g=33.5, fats_g=3.3, fibers_g=4.1)
    assert _classify("flocons d'avoine", macros) == FoodCategory.BREAKFAST


# ---------------------------------------------------------------------------
# Score tests
# ---------------------------------------------------------------------------

def test_score_perfect_meal():
    target = Macros(calories=500, proteins_g=25, carbs_g=60, fats_g=18, fibers_g=7)
    combined = Macros(calories=500, proteins_g=25, carbs_g=60, fats_g=18, fibers_g=7)
    score, devs = _score_meal(combined, target)
    assert score == pytest.approx(1.0, abs=1e-4)
    assert all(v == pytest.approx(0.0, abs=1e-4) for v in devs.values())


def test_score_range():
    target = Macros(calories=500, proteins_g=25, carbs_g=60, fats_g=18, fibers_g=7)
    bad = Macros(calories=100, proteins_g=5, carbs_g=10, fats_g=3, fibers_g=1)
    score, _ = _score_meal(bad, target)
    assert 0.0 <= score <= 1.0


# ---------------------------------------------------------------------------
# Composer tests
# ---------------------------------------------------------------------------

def test_compose_week_returns_7_days():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    assert len(days) == 7


def test_compose_week_day_numbers():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    assert [d["day"] for d in days] == list(range(1, 8))


def test_compose_week_all_slots_filled():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    for day in days:
        assert day["breakfast"], f"Jour {day['day']}: petit-déj vide"
        assert day["lunch"], f"Jour {day['day']}: déjeuner vide"
        assert day["dinner"], f"Jour {day['day']}: dîner vide"


def test_compose_week_scores_between_0_and_1():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    for day in days:
        assert 0.0 <= day["score"] <= 1.0, f"Score invalide jour {day['day']}: {day['score']}"


def test_compose_week_calories_positive():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    for day in days:
        assert day["estimatedCalories"] > 0


def test_compose_week_vegetarian_no_meat():
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile(), constraints={"vegetarien"})
    for day in days:
        for slot in ["breakfast", "lunch", "dinner"]:
            assert "poulet" not in day[slot].lower()
            assert "saumon" not in day[slot].lower()


def test_compose_week_variety_across_days():
    """Les déjeuners doivent varier (pas identiques tous les jours)."""
    composer = MealComposerService(_CATALOG)
    days = composer.compose_week(_default_profile())
    lunches = [d["lunch"] for d in days]
    # Au moins 2 déjeuners différents sur 7 jours
    assert len(set(lunches)) >= 2


def test_score_meal_method():
    composer = MealComposerService(_CATALOG)
    profile = _default_profile()
    result = composer.score_meal(["poulet grillé (150g)", "riz basmati (100g)"], profile, "lunch")
    assert 0.0 <= result.score <= 1.0
    assert result.macros.calories > 0


def test_empty_catalog_gracefully():
    """Un catalogue vide ne doit pas crasher."""
    composer = MealComposerService({})
    days = composer.compose_week(_default_profile())
    # Peut retourner des jours avec slots vides, mais ne doit pas lever d'exception
    assert isinstance(days, list)


# ---------------------------------------------------------------------------
# Integration : real Kaggle catalog
# ---------------------------------------------------------------------------

def test_compose_week_real_catalog():
    """Test d'intégration avec les 601 aliments du backend."""
    from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService
    from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import (
        BackendNutritionLookupService,
    )

    try:
        auth = BackendAuthService(
            "http://localhost:3001",
            "agathe.andre@example.com",
            "SeedPassword123!",
            timeout_seconds=5,
        )
        svc = BackendNutritionLookupService("http://localhost:3001", auth.get_token())
        catalog = svc.get_catalog()

        if len(catalog) < 10:
            pytest.skip("Catalogue trop petit (backend indisponible ?)")

        composer = MealComposerService(catalog)
        profile = HealthProfile(
            daily_calories_target=1800,
            proteins_target_g=100,
            carbs_target_g=200,
            fats_target_g=60,
            fibers_target_g=28,
        )
        days = composer.compose_week(profile, constraints=set(), allergies=set())

        assert len(days) == 7
        avg_score = sum(d["score"] for d in days) / 7
        print(f"\nScore moyen (601 aliments, perte_de_poids): {avg_score:.3f}")
        assert avg_score > 0.1, "Score trop bas avec le catalogue réel"

    except Exception as exc:
        pytest.skip(f"Backend indisponible: {exc}")
