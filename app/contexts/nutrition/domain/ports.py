"""Domain ports (Protocols) for the nutrition bounded context.

Use cases depend on these abstractions. Infrastructure implements them.
The domain never imports from infrastructure or application layers.
"""

from __future__ import annotations

from typing import Any, Protocol

from app.contexts.nutrition.domain.models import Macros, VisionDetection


class VisionProviderPort(Protocol):
    """Detects food items in an image."""

    async def detect_foods(
        self,
        image_url: str | None,
        image_base64: str | None,
    ) -> list[VisionDetection]: ...


class LlmProviderPort(Protocol):
    """Generates human-readable nutrition advice and meal plans."""

    async def generate_suggestions(
        self,
        goal: str,
        imbalance_tokens: list[str],
    ) -> list[str]: ...

    async def generate_meal_plan_text(
        self,
        goal: str,
        dietary_constraints: list[str],
        allergies: list[str],
        daily_calories: int,
    ) -> str | None: ...


class CachePort(Protocol):
    """Key/value cache with TTL."""

    def get(self, key: str) -> Any | None: ...
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None: ...
    def image_key(self, image_url: str | None, image_base64: str | None) -> str: ...
    def llm_key(self, goal: str, imbalance_tokens: list[str]) -> str: ...


class NutritionLookupPort(Protocol):
    """Estimates macronutrients from food labels and filters vision output."""

    def compute_macros(self, food_labels: list[str]) -> Macros: ...
    def is_food_label(self, label: str) -> bool: ...
