"""Cas limites du MealComposerService (filtres régime/allergies, scoring)."""

from app.contexts.nutrition.domain.meal_composer import MealComposerService
from app.contexts.nutrition.domain.models import HealthProfile


def _catalog():
    return {
        # protéines animales
        "poulet grillé": (165, 31, 0, 4, 0),
        "bœuf haché": (250, 26, 0, 15, 0),
        "saumon fumé": (208, 20, 0, 13, 0),
        # produits animaux (non-vegan)
        "fromage blanc": (98, 8, 4, 5, 0),
        "yaourt grec": (59, 10, 4, 0, 0),
        "œuf dur": (155, 13, 1, 11, 0),
        # protéines végétales
        "tofu mariné": (144, 15, 4, 8, 1),
        "lentilles cuites": (116, 9, 20, 0, 8),
        # glucides
        "riz complet": (130, 3, 28, 1, 2),
        "pain complet": (247, 13, 41, 3, 7),
        "flocons d'avoine": (380, 13, 67, 7, 10),
        # légumes
        "brocoli vapeur": (34, 3, 7, 0, 3),
        "epinards": (23, 3, 4, 0, 2),
        # allergène
        "beurre de cacahuète": (588, 25, 20, 50, 6),
        # aliment quasi sans valeur → doit être ignoré par _build_items
        "angostura bitters": (1, 0, 0, 0, 0),
    }


def test_near_zero_items_are_filtered_out():
    composer = MealComposerService(_catalog(), rng_seed=1)

    names = {item.name for item in composer._items}
    assert "angostura bitters" not in names
    assert "poulet grillé" in names


def test_compose_week_returns_seven_days():
    composer = MealComposerService(_catalog(), rng_seed=1)

    plan = composer.compose_week(HealthProfile())

    assert len(plan) == 7
    assert all("breakfast" in day and "estimatedCalories" in day for day in plan)


def test_vegetarian_excludes_meat_and_fish():
    composer = MealComposerService(_catalog(), rng_seed=1)

    plan = composer.compose_week(HealthProfile(), constraints={"vegetarien"})

    all_foods = " ".join(
        f"{d['breakfast']} {d['lunch']} {d['dinner']} {d.get('snack') or ''}"
        for d in plan
    ).lower()
    assert "poulet" not in all_foods
    assert "saumon" not in all_foods
    assert "bœuf" not in all_foods


def test_vegan_excludes_animal_products():
    composer = MealComposerService(_catalog(), rng_seed=1)

    plan = composer.compose_week(HealthProfile(), constraints={"vegan"})

    all_foods = " ".join(
        f"{d['breakfast']} {d['lunch']} {d['dinner']} {d.get('snack') or ''}"
        for d in plan
    ).lower()
    for animal in ("poulet", "saumon", "fromage", "yaourt", "œuf"):
        assert animal not in all_foods


def test_allergies_exclude_matching_foods():
    composer = MealComposerService(_catalog(), rng_seed=1)

    plan = composer.compose_week(HealthProfile(), allergies={"cacahuète"})

    all_foods = " ".join(
        f"{d['breakfast']} {d['lunch']} {d['dinner']} {d.get('snack') or ''}"
        for d in plan
    ).lower()
    assert "cacahuète" not in all_foods


def test_score_meal_empty_returns_zero():
    composer = MealComposerService(_catalog(), rng_seed=1)

    result = composer.score_meal(["aliment-inconnu"], HealthProfile())

    assert result.score == 0.0
    assert result.macros.calories == 0


def test_score_meal_known_foods():
    composer = MealComposerService(_catalog(), rng_seed=1)

    result = composer.score_meal(["poulet grillé", "riz complet"], HealthProfile())

    assert 0.0 <= result.score <= 1.0
    assert result.macros.calories > 0


def test_compose_week_with_zero_calorie_targets():
    # Cibles nulles → la mise à l'échelle des portions est court-circuitée.
    composer = MealComposerService(_catalog(), rng_seed=1)
    zero_profile = HealthProfile(
        daily_calories_target=0,
        proteins_target_g=0,
        carbs_target_g=0,
        fats_target_g=0,
        fibers_target_g=0,
    )

    plan = composer.compose_week(zero_profile)

    assert len(plan) == 7


def test_compose_slot_skips_invalid_category():
    composer = MealComposerService(_catalog(), rng_seed=1)
    target = composer._meal_target(HealthProfile(), "lunch")

    meal = composer._compose_slot(
        composer._items,
        ["categorie_invalide", "protein"],
        target,
        n_foods=2,
        exclude=[],
    )

    assert len(meal.foods) >= 1


def test_compose_slot_complement_pool_exhausted():
    # Catalogue minimal : moins d'aliments distincts que n_foods demandés
    # → la boucle de complément s'arrête (complement_pool vide).
    tiny = {
        "poulet grillé": (165, 31, 0, 4, 0),
        "riz complet": (130, 3, 28, 1, 2),
    }
    composer = MealComposerService(tiny, rng_seed=1)
    target = composer._meal_target(HealthProfile(), "lunch")

    meal = composer._compose_slot(
        composer._items, ["protein", "carb"], target, n_foods=3, exclude=[]
    )

    assert 1 <= len(meal.foods) <= 2
