"""Tests du composition root (Container) — câblage du lookup nutrition."""

from unittest.mock import patch

import httpx

from app.composition import container as container_mod
from app.composition.container import Container, get_container
from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import (
    BackendNutritionLookupService,
)
from app.contexts.nutrition.infrastructure.nutrition_lookup import (
    NutritionLookupService,
)


def test_get_container_is_cached():
    assert get_container() is get_container()


def test_container_wires_use_cases():
    c = Container()

    assert c.create_workout_program is not None
    assert c.submit_workout_feedback is not None
    assert c.analyze_meal is not None
    assert c.generate_meal_plan is not None


def test_backend_lookup_active_when_auth_succeeds():
    # Auth backend OK → le lookup nutrition utilise le backend NestJS.
    with patch.object(
        container_mod.BackendAuthService, "get_token", return_value="jwt-token"
    ):
        c = Container()

    lookup = c.analyze_meal._nutrition_lookup
    assert isinstance(lookup, BackendNutritionLookupService)


def test_falls_back_to_static_lookup_when_auth_fails():
    # Auth backend KO → fallback sur la table statique embarquée.
    with patch.object(
        container_mod.BackendAuthService,
        "get_token",
        side_effect=httpx.ConnectError("backend down"),
    ):
        c = Container()

    assert isinstance(c.analyze_meal._nutrition_lookup, NutritionLookupService)


def test_falls_back_on_runtime_error():
    with patch.object(
        container_mod.BackendAuthService,
        "get_token",
        side_effect=RuntimeError("no token"),
    ):
        c = Container()

    assert isinstance(c.analyze_meal._nutrition_lookup, NutritionLookupService)
