"""Tests du branchement MealTypeModel dans MealComposerService (signal additif)."""

from app.contexts.nutrition.domain.meal_composer import (
    FoodCategory,
    MealComposerService,
)
from app.contexts.nutrition.domain.models import HealthProfile


def _catalog():
    return {
        "riz complet": (130, 3, 28, 1, 2, 0, 0, 0),
        "poulet grillé": (165, 31, 0, 4, 0, 0, 0, 0),
        "yaourt nature": (59, 3.5, 4.7, 3.3, 0, 4.7, 36, 13),
        "amandes": (579, 21, 22, 50, 12, 4.4, 1, 0),
    }


class _FakeModelAllBreakfast:
    """Prédit toujours "Petit-déjeuner", quel que soit l'aliment."""

    def predict(self, x):
        return ["Petit-déjeuner"] * len(x)


class _FakeModelByIndex:
    """Prédit un label différent par position (ordre du dict catalog)."""

    def __init__(self, labels: list[str]):
        self._labels = labels

    def predict(self, x):
        return self._labels[: len(x)]


class _FakeModelRaises:
    def predict(self, x):
        raise RuntimeError("modèle corrompu")


def test_predicted_meal_type_is_none_when_no_model_trained_yet(monkeypatch):
    # Simule l'absence de modèle entraîné (fichier .joblib manquant) — c'est le
    # scénario réel de fallback, distinct de "passer None explicitement" (qui
    # déclenche le chargement du modèle par défaut s'il existe sur disque).
    import app.contexts.nutrition.domain.meal_composer as meal_composer_module

    monkeypatch.setattr(
        meal_composer_module.MealTypeModel,
        "load",
        classmethod(lambda cls, *a, **k: None),
    )

    composer = MealComposerService(_catalog(), rng_seed=1)

    assert all(item.predicted_meal_type is None for item in composer._items)
    assert composer._by_predicted_meal_type == {}


def test_predicted_meal_type_is_set_when_model_available():
    composer = MealComposerService(
        _catalog(),
        rng_seed=1,
        meal_type_model=_FakeModelAllBreakfast(),
    )

    assert all(item.predicted_meal_type == "Petit-déjeuner" for item in composer._items)
    assert len(composer._by_predicted_meal_type["Petit-déjeuner"]) == len(
        composer._items,
    )


def test_model_prediction_failure_is_safe():
    composer = MealComposerService(
        _catalog(),
        rng_seed=1,
        meal_type_model=_FakeModelRaises(),
    )

    assert all(item.predicted_meal_type is None for item in composer._items)


def test_compose_slot_enriches_pool_via_ml_when_category_pool_insufficient():
    # "amandes" est classé MIXED par l'heuristique (pas BREAKFAST/CARB), donc
    # absent du pool breakfast par défaut. Le modèle (fake) prédit pourtant
    # "Petit-déjeuner" pour lui : il doit pouvoir être sélectionné au petit-déj
    # une fois les candidats heuristiques épuisés.
    catalog = {"amandes": (579, 21, 22, 50, 12, 4.4, 1, 0)}
    composer = MealComposerService(
        catalog,
        rng_seed=1,
        meal_type_model=_FakeModelAllBreakfast(),
    )
    assert composer._items[0].category != FoodCategory.BREAKFAST

    profile = HealthProfile()
    meal = composer._compose_slot(
        composer._items,
        category_priority=["breakfast", "carb"],
        target=composer._meal_target(profile, "breakfast"),
        n_foods=1,
        exclude=[],
        slot="breakfast",
    )

    assert meal.foods  # le repli ML a bien fourni un candidat
    assert "amandes" in meal.foods[0]


def test_compose_slot_without_slot_param_skips_ml_enrichment():
    catalog = {"amandes": (579, 21, 22, 50, 12, 4.4, 1, 0)}
    composer = MealComposerService(
        catalog,
        rng_seed=1,
        meal_type_model=_FakeModelAllBreakfast(),
    )
    profile = HealthProfile()

    # Sans `slot`, l'enrichissement ML est sauté — seuls les fallbacks
    # heuristiques s'appliquent (mais ils suffisent ici car "tous les permis"
    # retombe sur le seul aliment du catalogue).
    meal = composer._compose_slot(
        composer._items,
        category_priority=["breakfast", "carb"],
        target=composer._meal_target(profile, "breakfast"),
        n_foods=1,
        exclude=[],
    )
    assert meal.foods
