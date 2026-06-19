"""Tests d'intégration de MongoNutritionLookupService contre un vrai MongoDB.

Marqués ``integration`` et ignorés automatiquement si la base est indisponible.

    pytest -m integration
"""

import pytest

from app.config import settings
from app.contexts.nutrition.infrastructure.mongo_nutrition_lookup import (
    MongoNutritionLookupService,
)
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database

pytestmark = pytest.mark.integration

_TEST_URI = (
    "mongodb://localhost:27017/healthai_coach_test?serverSelectionTimeoutMS=1500"
)


def _doc(name, kcal, p, c, f, fib, aliases=None):
    return {
        "name": name,
        "aliases": aliases or [],
        "calories_kcal": kcal,
        "protein_g": p,
        "carbohydrates_g": c,
        "fat_g": f,
        "fiber_g": fib,
    }


@pytest.fixture
async def mongo_db(monkeypatch):
    monkeypatch.setattr(settings, "environment", "integration")
    monkeypatch.setattr(settings, "mongodb_uri", _TEST_URI)

    try:
        await database.connect_mongodb()
        available = await database.ping_mongodb()
    except Exception:
        available = False

    if not available:
        await database.close_mongodb()
        pytest.skip("MongoDB indisponible — test d'intégration ignoré")

    db = database.get_database()
    await db[col.NUTRITION_FOODS].delete_many({})
    await db[col.NUTRITION_FOODS].insert_many(
        [
            _doc("poulet", 165, 31.0, 0.0, 3.6, 0.0, aliases=["chicken"]),
            _doc("riz", 130, 2.7, 28.0, 0.3, 0.4, aliases=["rice"]),
            _doc("brocoli", 34, 2.8, 7.0, 0.4, 2.6),
        ]
    )

    yield db

    await db[col.NUTRITION_FOODS].delete_many({})
    await database.close_mongodb()


async def test_resolves_each_food_of_a_dish_from_mongo(mongo_db):
    service = MongoNutritionLookupService()

    # Plat = poulet + riz + brocoli ; chaque élément doit être reconnu.
    macros = await service.compute_macros(["poulet", "riz", "brocoli"], serving_g=100.0)

    assert macros.estimated is False
    assert macros.calories == 329  # 165 + 130 + 34
    assert macros.proteins_g == 36.5  # 31 + 2.7 + 2.8


async def test_alias_and_plural_resolution_from_mongo(mongo_db):
    service = MongoNutritionLookupService()

    # Label anglais (alias) + pluriel → reconnus depuis la base.
    macros = await service.compute_macros(["chicken", "rice"], serving_g=100.0)
    assert macros.estimated is False
    assert macros.calories == 295

    assert service.resolve_food_name("Chicken") == "chicken"


async def test_get_catalog_reflects_inserted_foods(mongo_db):
    service = MongoNutritionLookupService()

    catalog = await service.get_catalog()

    # Noms + alias normalisés présents dans le catalogue chargé.
    assert {"poulet", "riz", "brocoli", "chicken", "rice"} <= set(catalog)
