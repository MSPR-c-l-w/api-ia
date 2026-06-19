"""Tests du composition root (Container) — câblage du lookup nutrition."""

from app.composition.container import Container, get_container
from app.contexts.nutrition.infrastructure.mongo_nutrition_lookup import (
    MongoNutritionLookupService,
)


def test_get_container_is_cached():
    assert get_container() is get_container()


def test_container_wires_use_cases():
    c = Container()

    assert c.create_workout_program is not None
    assert c.submit_workout_feedback is not None
    assert c.analyze_meal is not None
    assert c.generate_meal_plan is not None


def test_nutrition_lookup_is_mongo_backed():
    # Le catalogue d'aliments est servi depuis MongoDB (fallback statique intégré).
    c = Container()

    assert isinstance(c.analyze_meal._nutrition_lookup, MongoNutritionLookupService)
    assert isinstance(
        c.generate_meal_plan._nutrition_lookup, MongoNutritionLookupService
    )
