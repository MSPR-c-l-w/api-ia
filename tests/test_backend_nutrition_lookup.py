"""Tests unitaires de BackendNutritionLookupService.

Vérifie la résolution des macros (cache, word-boundary, fallback statique) et
le chargement paginé depuis le backend (httpx.AsyncClient simulé).
"""

import httpx

from app.contexts.nutrition.infrastructure import backend_nutrition_lookup
from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import (
    BackendNutritionLookupService,
)


class _FakeAsyncClient:
    """Faux client : route les GET selon le paramètre ``limit``.

    - ``limit == 1`` → renvoie ``{"total": ...}``
    - sinon → renvoie une page de ``{"data": [...]}``
    """

    def __init__(self, total: int, pages: dict[int, list[dict]], raise_exc=None):
        self._total = total
        self._pages = pages
        self._raise = raise_exc

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, params=None, headers=None):
        if self._raise is not None:
            raise self._raise
        req = httpx.Request("GET", url)
        if params and params.get("limit") == 1:
            return httpx.Response(200, json={"total": self._total}, request=req)
        page = params.get("page", 1) if params else 1
        return httpx.Response(
            200, json={"data": self._pages.get(page, [])}, request=req
        )


def _patch_client(monkeypatch, **kwargs):
    monkeypatch.setattr(
        backend_nutrition_lookup.httpx,
        "AsyncClient",
        _FakeAsyncClient(**kwargs),
    )


def _item(name, kcal=100, p=10, c=20, f=5, fib=3):
    return {
        "name": name,
        "calories_kcal": kcal,
        "protein_g": p,
        "carbohydrates_g": c,
        "fat_g": f,
        "fiber_g": fib,
    }


# ---------------------------------------------------------------------------
# Chargement depuis le backend
# ---------------------------------------------------------------------------


async def test_get_catalog_loads_from_backend(monkeypatch):
    _patch_client(
        monkeypatch,
        total=2,
        pages={1: [_item("poulet", kcal=165), _item("riz", kcal=130)]},
    )
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    catalog = await service.get_catalog()

    assert set(catalog) == {"poulet", "riz"}
    assert catalog["poulet"][0] == 165.0


async def test_compute_macros_scales_by_serving(monkeypatch):
    _patch_client(monkeypatch, total=1, pages={1: [_item("poulet", kcal=200, p=20)]})
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    macros = await service.compute_macros(["poulet"], serving_g=200.0)

    # 200 kcal/100g × 200g = 400 kcal
    assert macros.calories == 400
    assert macros.proteins_g == 40.0
    assert macros.estimated is False


async def test_word_boundary_match(monkeypatch):
    _patch_client(monkeypatch, total=1, pages={1: [_item("riz")]})
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    macros = await service.compute_macros(["riz complet"], serving_g=100.0)

    # "riz" est trouvé dans "riz complet" via word-boundary → pas estimé.
    assert macros.estimated is False


async def test_pagination_stops_on_partial_page(monkeypatch):
    full = [_item(f"aliment{i}") for i in range(100)]
    _patch_client(
        monkeypatch,
        total=150,
        pages={1: full, 2: [_item("dernier")]},
    )
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    catalog = await service.get_catalog()

    assert len(catalog) == 101
    assert "dernier" in catalog


async def test_empty_backend_falls_back_to_static(monkeypatch):
    _patch_client(monkeypatch, total=0, pages={})
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    catalog = await service.get_catalog()

    assert catalog == {}
    # La résolution retombe sur la table statique embarquée.
    macros = await service.compute_macros(["poulet"], serving_g=100.0)
    assert macros.calories > 0


async def test_backend_error_falls_back_to_static(monkeypatch):
    _patch_client(monkeypatch, total=0, pages={}, raise_exc=httpx.ConnectError("x"))
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    # Aucune exception ne doit remonter : fallback silencieux.
    macros = await service.compute_macros(["poulet"], serving_g=100.0)

    assert macros.calories > 0
    # Le backoff évite de re-tenter immédiatement.
    assert service._loaded_at != 0.0


async def test_unknown_food_marked_estimated(monkeypatch):
    _patch_client(monkeypatch, total=1, pages={1: [_item("poulet")]})
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    macros = await service.compute_macros(["aliment-totalement-inconnu-xyz"])

    assert macros.estimated is True


def test_is_food_label_delegates_to_fallback():
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    assert service.is_food_label("poulet") is True


async def test_cache_avoids_second_backend_load(monkeypatch):
    client = _FakeAsyncClient(total=1, pages={1: [_item("poulet")]})
    monkeypatch.setattr(backend_nutrition_lookup.httpx, "AsyncClient", client)
    service = BackendNutritionLookupService("http://backend:3001", "jwt")

    await service.get_catalog()
    loaded_at = service._loaded_at
    await service.get_catalog()  # cache encore valide

    assert service._loaded_at == loaded_at
