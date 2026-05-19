"""Unit tests for AI cache service (#91) and nutrition lookup (#86)."""

import time

from app.contexts.nutrition.infrastructure.cache import AiCacheService
from app.contexts.nutrition.infrastructure.nutrition_lookup import (
    NutritionLookupService,
    is_food_label,
)


# ---------------------------------------------------------------------------
# Cache tests
# ---------------------------------------------------------------------------


def test_cache_set_and_get():
    cache = AiCacheService()
    cache.set("key1", {"foods": ["poulet"]}, ttl_seconds=60)
    result = cache.get("key1")
    assert result == {"foods": ["poulet"]}


def test_cache_miss_returns_none():
    cache = AiCacheService()
    assert cache.get("nonexistent") is None


def test_cache_expired_entry_returns_none():
    cache = AiCacheService()
    # Force an immediately-expired entry by setting TTL = 0
    cache.set("k", "val", ttl_seconds=0)
    time.sleep(0.01)
    assert cache.get("k") is None


def test_cache_hit_miss_counters():
    cache = AiCacheService()
    cache.set("x", 42, ttl_seconds=60)
    cache.get("x")  # hit
    cache.get("y")  # miss
    assert cache.stats["hits"] == 1
    assert cache.stats["misses"] == 1


def test_cache_image_key_stable():
    cache = AiCacheService()
    k1 = cache.image_key("https://example.com/a.jpg", None)
    k2 = cache.image_key("https://example.com/a.jpg", None)
    assert k1 == k2
    assert k1.startswith("img:")


def test_cache_llm_key_order_independent():
    cache = AiCacheService()
    k1 = cache.llm_key("perte_de_poids", ["calories_EXCES", "proteins_g_DEFICIT"])
    k2 = cache.llm_key("perte_de_poids", ["proteins_g_DEFICIT", "calories_EXCES"])
    assert k1 == k2


def test_cache_avoids_second_api_call():
    """Verify that a cached detection result is returned without re-querying."""
    cache = AiCacheService()
    key = cache.image_key("https://example.com/meal.jpg", None)

    # Pre-populate cache
    fake_result = [{"label": "poulet", "confidence": 0.9}]
    cache.set(key, fake_result, ttl_seconds=3600)

    # Retrieval should be a hit
    cached = cache.get(key)
    assert cached == fake_result
    assert cache.stats["hits"] == 1
    assert cache.stats["misses"] == 0


# ---------------------------------------------------------------------------
# Nutrition lookup tests
# ---------------------------------------------------------------------------


def test_lookup_known_food_not_estimated():
    svc = NutritionLookupService()
    _, estimated = svc.lookup("poulet grillé")
    assert not estimated


def test_lookup_unknown_food_is_estimated():
    svc = NutritionLookupService()
    _, estimated = svc.lookup("spaghetti bolognaise alien")
    assert estimated


def test_compute_macros_single_known_food():
    svc = NutritionLookupService()
    macros = svc.compute_macros(["riz"], serving_g=100)
    # riz per 100g: 130 kcal, 2.7 prot, 28 carbs, 0.3 fat, 0.4 fiber
    assert macros.calories == 130
    assert macros.proteins_g == 2.7
    assert not macros.estimated


def test_compute_macros_empty_list():
    svc = NutritionLookupService()
    macros = svc.compute_macros([])
    assert macros.calories == 0
    assert macros.proteins_g == 0.0


def test_compute_macros_unknown_food_flagged():
    svc = NutritionLookupService()
    macros = svc.compute_macros(["mystery_ingredient_xyz"])
    assert macros.estimated


def test_compute_macros_mixed_list():
    svc = NutritionLookupService()
    macros = svc.compute_macros(["poulet", "mystery_ingredient_xyz"])
    assert macros.estimated  # at least one unknown → estimated


# ---------------------------------------------------------------------------
# Non-food filter tests
# ---------------------------------------------------------------------------


def test_is_food_label_accepts_real_food():
    assert is_food_label("poulet rôti")
    assert is_food_label("rice")
    assert is_food_label("saumon grillé")


def test_is_food_label_rejects_non_food():
    assert not is_food_label("plate")
    assert not is_food_label("fork")
    assert not is_food_label("bowl")
    assert not is_food_label("tablecloth")
    assert not is_food_label("restaurant background")
