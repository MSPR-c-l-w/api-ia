"""Tests unitaires de MongoNutritionLookupService.

Couvre la résolution des macros depuis un catalogue MongoDB simulé :
matching exact, frontière de mot, tolérance singulier/pluriel, insensibilité
aux accents, alias, plat multi-aliments, et fallback statique quand Mongo est
indisponible ou vide.
"""

from app.contexts.nutrition.infrastructure import mongo_nutrition_lookup
from app.contexts.nutrition.infrastructure.mongo_nutrition_lookup import (
    MongoNutritionLookupService,
)

# ---------------------------------------------------------------------------
# Faux MongoDB (cursor asynchrone)
# ---------------------------------------------------------------------------


class _FakeCursor:
    def __init__(self, docs):
        self._docs = docs

    def __aiter__(self):
        async def _gen():
            for doc in self._docs:
                yield doc

        return _gen()


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, _query=None, _projection=None):
        return _FakeCursor(self._docs)


class _FakeDB:
    def __init__(self, docs):
        self._coll = _FakeCollection(docs)

    def __getitem__(self, _name):
        return self._coll


def _doc(name, kcal=100, p=10, c=20, f=5, fib=3, aliases=None, category=None):
    return {
        "name": name,
        "aliases": aliases or [],
        "category": category,
        "calories_kcal": kcal,
        "protein_g": p,
        "carbohydrates_g": c,
        "fat_g": f,
        "fiber_g": fib,
    }


def _patch_mongo(monkeypatch, docs):
    monkeypatch.setattr(
        mongo_nutrition_lookup.database,
        "get_database",
        lambda: _FakeDB(docs),
    )


# ---------------------------------------------------------------------------
# Chargement & calcul depuis Mongo
# ---------------------------------------------------------------------------


async def test_get_catalog_loads_from_mongo(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("poulet", kcal=165), _doc("riz", kcal=130)])
    service = MongoNutritionLookupService()

    catalog = await service.get_catalog()

    assert set(catalog) == {"poulet", "riz"}
    assert catalog["poulet"][0] == 165.0


async def test_compute_macros_scales_by_serving(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("poulet", kcal=200, p=20)])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["poulet"], serving_g=200.0)

    # 200 kcal/100g × 200 g = 400 kcal
    assert macros.calories == 400
    assert macros.proteins_g == 40.0
    assert macros.estimated is False


async def test_multi_food_dish_aggregates_each_element(monkeypatch):
    _patch_mongo(
        monkeypatch,
        [_doc("poulet", kcal=165, p=31), _doc("riz", kcal=130, p=2.7)],
    )
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["poulet", "riz"], serving_g=100.0)

    # Les deux aliments du plat sont reconnus et additionnés.
    assert macros.calories == 295  # 165 + 130
    assert macros.proteins_g == 33.7  # 31 + 2.7
    assert macros.estimated is False


async def test_plural_label_is_recognised(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("oeuf", kcal=155)])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["oeufs"], serving_g=100.0)

    # "oeufs" (pluriel) → reconnu via la tolérance singulier/pluriel.
    assert macros.estimated is False
    assert macros.calories == 155


async def test_accent_insensitive_match(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("pâtes", kcal=131)])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["Pates"], serving_g=100.0)

    assert macros.estimated is False
    assert macros.calories == 131


async def test_backend_data_takes_precedence_over_static(monkeypatch):
    # Même aliment des deux côtés : la table backend (ETL) doit primer.
    _patch_mongo(
        monkeypatch,
        [
            _doc("fromage", kcal=402, category="static"),
            _doc(
                "Fromage blanc 0% 100g",
                kcal=45,
                aliases=["fromage"],
                category="Produits laitiers",
            ),
        ],
    )
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["fromage"], serving_g=100.0)

    assert macros.calories == 45  # valeur de la table backend, pas la statique (402)


async def test_alias_resolves_to_same_macros(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("poulet", kcal=165, aliases=["chicken"])])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["chicken"], serving_g=100.0)

    assert macros.estimated is False
    assert macros.calories == 165


async def test_word_boundary_match_in_dish_label(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("riz", kcal=130)])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["riz complet"], serving_g=100.0)

    # "riz" trouvé dans "riz complet" via frontière de mot.
    assert macros.estimated is False


async def test_resolve_food_name_returns_canonical(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("poulet", aliases=["chicken"])])
    service = MongoNutritionLookupService()
    await service.get_catalog()  # force le chargement

    assert service.resolve_food_name("Chicken") == "chicken"
    assert service.resolve_food_name("riz complet") is None


async def test_unknown_food_marked_estimated(monkeypatch):
    _patch_mongo(monkeypatch, [_doc("poulet")])
    service = MongoNutritionLookupService()

    macros = await service.compute_macros(["aliment-totalement-inconnu-xyz"])

    assert macros.estimated is True


# ---------------------------------------------------------------------------
# Fallback statique
# ---------------------------------------------------------------------------


async def test_empty_collection_falls_back_to_static(monkeypatch):
    _patch_mongo(monkeypatch, [])
    service = MongoNutritionLookupService()

    # Collection vide → fallback table statique embarquée.
    macros = await service.compute_macros(["poulet"], serving_g=100.0)

    assert macros.calories > 0


async def test_mongo_unavailable_falls_back_to_static(monkeypatch):
    def _raise():
        raise RuntimeError("MongoDB non initialisé")

    monkeypatch.setattr(mongo_nutrition_lookup.database, "get_database", _raise)
    service = MongoNutritionLookupService()

    # Aucune exception ne doit remonter : fallback silencieux.
    macros = await service.compute_macros(["poulet"], serving_g=100.0)

    assert macros.calories > 0
    # Backoff posé pour éviter de re-tenter immédiatement.
    assert service._loaded_at != 0.0


def test_is_food_label_delegates_to_fallback():
    service = MongoNutritionLookupService()

    assert service.is_food_label("poulet") is True
    assert service.is_food_label("plate") is False


async def test_cache_avoids_second_mongo_load(monkeypatch):
    calls = {"count": 0}

    def _counting_get_db():
        calls["count"] += 1
        return _FakeDB([_doc("poulet")])

    monkeypatch.setattr(
        mongo_nutrition_lookup.database, "get_database", _counting_get_db
    )
    service = MongoNutritionLookupService()

    await service.get_catalog()
    await service.get_catalog()  # cache encore valide

    assert calls["count"] == 1
