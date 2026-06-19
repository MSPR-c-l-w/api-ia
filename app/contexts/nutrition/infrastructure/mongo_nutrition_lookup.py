"""Adaptateur nutrition — résout les macros depuis MongoDB (`nutrition_foods`).

Stratégie :
  1. Charge le catalogue depuis MongoDB (cache mémoire, TTL configurable).
  2. Résolution d'un label détecté :
       - normalisation (minuscules, accents retirés, espaces compactés) ;
       - correspondance exacte, puis par frontière de mot avec tolérance
         singulier/pluriel, dans les deux sens (label↔catalogue) ;
       - prise en compte des alias (ex. "chicken" → "poulet").
  3. Fallback automatique sur la table statique embarquée si MongoDB est
     indisponible ou si la collection est vide.

Le but est de reconnaître correctement chaque élément issu d'un plat même quand
le modèle de vision renvoie une variante (pluriel, langue, accent).
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata

from app.contexts.nutrition.domain.models import Macros
from app.contexts.nutrition.infrastructure.nutrition_lookup import (
    _DEFAULT,
    DEFAULT_SERVING_G,
    NutritionLookupService,
)
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes
_BACKOFF_TTL_SECONDS = 30  # ré-essai après 30 s en cas d'échec

# Macros = (calories, proteins_g, carbs_g, fats_g, fibers_g) pour 100 g
_Macro5 = tuple[float, float, float, float, float]


def _normalise(value: str) -> str:
    """Minuscule + suppression des accents + espaces compactés."""
    decomposed = unicodedata.normalize("NFKD", value.lower().strip())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", without_accents)


class MongoNutritionLookupService:
    """NutritionLookupPort alimenté par la collection MongoDB ``nutrition_foods``."""

    def __init__(self, ttl_seconds: int = _CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._fallback = NutritionLookupService()
        # {nom_normalisé: macros pour 100 g}
        self._table: dict[str, _Macro5] = {}
        # patterns pré-compilés avec tolérance pluriel (suffixe « s? »)
        self._compiled_patterns: dict[str, re.Pattern[str]] = {}
        self._loaded_at: float = 0.0

    # ------------------------------------------------------------------
    # NutritionLookupPort
    # ------------------------------------------------------------------

    async def compute_macros(
        self, food_labels: list[str], serving_g: float = DEFAULT_SERVING_G
    ) -> Macros:
        await self._ensure_loaded()
        totals = [0.0, 0.0, 0.0, 0.0, 0.0]
        any_estimated = False

        for food in food_labels:
            per_100g, estimated = self._lookup(food)
            any_estimated = any_estimated or estimated
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

    async def get_catalog(self) -> dict[str, _Macro5]:
        await self._ensure_loaded()
        return dict(self._table)

    def resolve_food_name(self, label: str) -> str | None:
        """Retourne le nom de catalogue correspondant au label, ou ``None``.

        Permet à la couche présentation de renvoyer le nom canonique de
        l'aliment reconnu (ex. "chicken" → "poulet") plutôt que le label brut.
        """
        normalised = _normalise(label)
        if not normalised:
            return None
        if normalised in self._table:
            return normalised
        label_re = re.compile(r"\b" + re.escape(normalised) + r"s?\b")
        for key, key_re in self._compiled_patterns.items():
            if key_re.search(normalised) or label_re.search(key):
                return key
        return None

    # ------------------------------------------------------------------
    # Internes
    # ------------------------------------------------------------------

    def _lookup(self, food_name: str) -> tuple[_Macro5, bool]:
        normalised = _normalise(food_name)

        # 1. Correspondance exacte (chemin le plus rapide)
        if normalised in self._table:
            return self._table[normalised], False

        # 2. Correspondance par frontière de mot (tolérance pluriel, deux sens)
        if normalised:
            label_re = re.compile(r"\b" + re.escape(normalised) + r"s?\b")
            for key, key_re in self._compiled_patterns.items():
                if key_re.search(normalised) or label_re.search(key):
                    return self._table[key], False

        # 3. Fallback : table statique embarquée
        static_macros, static_estimated = self._fallback.lookup(food_name)
        if not static_estimated:
            return static_macros, False

        logger.debug("Aliment '%s' introuvable — valeurs par défaut.", food_name)
        return _DEFAULT, True

    async def _ensure_loaded(self) -> None:
        if time.time() - self._loaded_at < self._ttl:
            return
        try:
            await self._load_from_mongo()
        except Exception as exc:
            logger.warning(
                "MongoNutritionLookup: chargement impossible (%s). Fallback statique.",
                exc,
            )
            # Throttle : évite de marteler Mongo à chaque requête.
            self._loaded_at = time.time() - self._ttl + _BACKOFF_TTL_SECONDS

    async def _load_from_mongo(self) -> None:
        try:
            db = database.get_database()
        except RuntimeError as exc:
            raise RuntimeError("MongoDB non initialisé") from exc

        projection = {
            "name": 1,
            "aliases": 1,
            "calories_kcal": 1,
            "protein_g": 1,
            "carbohydrates_g": 1,
            "fat_g": 1,
            "fiber_g": 1,
        }

        new_table: dict[str, _Macro5] = {}
        async for item in db[col.NUTRITION_FOODS].find({}, projection):
            name = _normalise(item.get("name") or "")
            if not name:
                continue
            macros: _Macro5 = (
                float(item.get("calories_kcal") or 0),
                float(item.get("protein_g") or 0),
                float(item.get("carbohydrates_g") or 0),
                float(item.get("fat_g") or 0),
                float(item.get("fiber_g") or 0),
            )
            new_table[name] = macros
            # Les alias pointent vers les mêmes macros (sans écraser un nom réel).
            for alias in item.get("aliases") or []:
                alias_norm = _normalise(str(alias))
                if alias_norm:
                    new_table.setdefault(alias_norm, macros)

        if not new_table:
            raise RuntimeError("collection nutrition_foods vide")

        self._table = new_table
        self._compiled_patterns = {
            key: re.compile(r"\b" + re.escape(key) + r"s?\b") for key in new_table
        }
        self._loaded_at = time.time()
        logger.info(
            "MongoNutritionLookup: %d entrées chargées depuis MongoDB.", len(new_table)
        )
