"""Adaptateur nutrition — récupère les données depuis le backend NestJS.

Stratégie :
  1. Appel HTTP GET /nutrition?page=1&limit=500 sur le backend (JWT service account).
  2. Si le backend est indisponible ou renvoie une erreur, fallback sur la table statique.
  3. Le catalogue est mis en cache en mémoire (TTL configurable, défaut 10 min).
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import httpx

from app.contexts.nutrition.domain.models import Macros
from app.contexts.nutrition.infrastructure.nutrition_lookup import (
    DEFAULT_SERVING_G,
    NutritionLookupService,
    _DEFAULT,
    _NON_FOOD_TOKENS,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes


class BackendNutritionLookupService:
    """NutritionLookupPort alimenté par le backend NestJS.

    Résout les macros depuis la table ``Nutrition`` du backend (données Kaggle
    importées + validées).  Fallback automatique sur la table statique si le
    backend est indisponible.
    """

    def __init__(
        self,
        backend_url: str,
        access_token: str,
        timeout_seconds: int = 5,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._access_token = access_token
        self._timeout = timeout_seconds
        self._fallback = NutritionLookupService()

        # In-memory cache: {normalised_name: (calories, proteins, carbs, fats, fibers)}
        self._table: dict[str, tuple[float, float, float, float, float]] = {}
        self._loaded_at: float = 0.0

    # ------------------------------------------------------------------
    # NutritionLookupPort interface
    # ------------------------------------------------------------------

    def compute_macros(
        self,
        food_labels: list[str],
        serving_g: float = DEFAULT_SERVING_G,
    ) -> Macros:
        self._ensure_loaded()
        totals = [0.0, 0.0, 0.0, 0.0, 0.0]
        any_estimated = False

        for food in food_labels:
            per_100g, estimated = self._lookup(food)
            if estimated:
                any_estimated = True
            factor = serving_g / 100.0
            for i, val in enumerate(per_100g):
                totals[i] += val * factor

        return Macros(
            calories=round(totals[0]),
            proteins_g=round(totals[1], 1),
            carbs_g=round(totals[2], 1),
            fats_g=round(totals[3], 1),
            fibers_g=round(totals[4], 1),
            estimated=any_estimated,
        )

    def is_food_label(self, label: str) -> bool:
        return self._fallback.is_food_label(label)

    def get_catalog(self) -> dict[str, tuple[float, float, float, float, float]]:
        """Return the full backend catalog (loads from backend if needed)."""
        self._ensure_loaded()
        return dict(self._table)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lookup(
        self, food_name: str
    ) -> tuple[tuple[float, float, float, float, float], bool]:
        normalised = food_name.lower().strip()

        # 1. Exact match (fastest path)
        if normalised in self._table:
            return self._table[normalised], False

        # 2. Word-boundary match to avoid false positives (e.g. "chick" matching "chicken")
        for key, macros in self._table.items():
            key_pattern = r"\b" + re.escape(key) + r"\b"
            val_pattern = r"\b" + re.escape(normalised) + r"\b"
            if re.search(key_pattern, normalised) or re.search(val_pattern, key):
                return macros, False

        # 3. Fallback: static embedded table
        static_result = self._fallback.lookup(food_name)
        if not static_result[1]:  # found in static table
            return static_result

        logger.debug("Food '%s' not found anywhere — using defaults", food_name)
        return _DEFAULT, True

    def _ensure_loaded(self) -> None:
        """Reload catalog from backend if cache is stale."""
        if time.time() - self._loaded_at < _CACHE_TTL_SECONDS:
            return
        try:
            self._load_from_backend()
        except Exception as exc:
            logger.warning(
                "BackendNutritionLookup: impossible de charger depuis le backend (%s)."
                " Fallback sur table statique.",
                exc,
            )

    def _load_from_backend(self) -> None:
        """Fetch all validated nutrition items from backend and populate _table."""
        url = f"{self._backend_url}/nutrition"
        headers = {"Authorization": f"Bearer {self._access_token}"}

        # First request to get total count
        resp = httpx.get(
            url,
            params={"page": 1, "limit": 1},
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        total: int = resp.json().get("total", 0)

        if total == 0:
            logger.warning("BackendNutritionLookup: aucun item en base, fallback statique.")
            return

        # Fetch all items page by page (backend max limit = 100)
        items: list[dict[str, Any]] = []
        page_size = 100
        for page in range(1, (total // page_size) + 2):
            resp = httpx.get(
                url,
                params={"page": page, "limit": page_size},
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
            batch: list[dict[str, Any]] = resp.json().get("data", [])
            items.extend(batch)
            if len(batch) < page_size:
                break

        new_table: dict[str, tuple[float, float, float, float, float]] = {}
        for item in items:
            name: str = (item.get("name") or "").lower().strip()
            if not name:
                continue
            new_table[name] = (
                float(item.get("calories_kcal") or 0),
                float(item.get("protein_g") or 0),
                float(item.get("carbohydrates_g") or 0),
                float(item.get("fat_g") or 0),
                float(item.get("fiber_g") or 0),
            )

        self._table = new_table
        self._loaded_at = time.time()
        logger.info(
            "BackendNutritionLookup: %d aliments chargés depuis le backend.", len(new_table)
        )
