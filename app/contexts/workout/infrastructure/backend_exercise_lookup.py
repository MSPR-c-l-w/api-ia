"""Adaptateur exercices — récupère le catalogue depuis le backend NestJS.

Stratégie :
  1. Appel HTTP GET /exercise?page=1&limit=100 sur le backend (JWT service account).
  2. Si le backend est indisponible ou renvoie une erreur, fallback sur EXERCISE_CATALOG.
  3. Le catalogue est mis en cache en mémoire (TTL 10 min).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.contexts.workout.domain.data.exercises_catalog import EXERCISE_CATALOG
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 600  # 10 minutes
_BACKOFF_TTL_SECONDS = 30

# Données stockées en français (ETL translate avant insertion)
_LEVEL_MAP: dict[str, str] = {
    "débutant": "debutant",
    "intermédiaire": "intermediaire",
    "expert": "avance",
    # Fallback anglais (données brutes non traduites)
    "beginner": "debutant",
    "intermediate": "intermediaire",
}

_MUSCLE_GROUP_MAP: dict[str, str] = {
    # Français (stocké après traduction ETL)
    "pectoraux": "pectoraux",
    "abdominaux": "core",
    "ischio-jambiers": "jambes",
    "adducteurs": "jambes",
    "abducteurs": "jambes",
    "quadriceps": "jambes",
    "biceps": "bras",
    "épaules": "epaules",
    "milieu du dos": "dos",
    "lombaires": "dos",
    "dorsaux": "dos",
    "triceps": "bras",
    "trapèzes": "dos",
    "avant-bras": "bras",
    "fessiers": "fessiers",
    "mollets": "jambes",
    "cou": "dos",
    # Anglais (fallback si non traduit)
    "chest": "pectoraux",
    "back": "dos",
    "lats": "dos",
    "lower back": "dos",
    "middle back": "dos",
    "traps": "dos",
    "shoulders": "epaules",
    "forearms": "bras",
    "hamstrings": "jambes",
    "calves": "jambes",
    "glutes": "fessiers",
    "abdominals": "core",
    "neck": "dos",
    "adductors": "jambes",
    "abductors": "jambes",
}

# Équipement "poids du corps" ou inconnu → liste vide (toujours disponible)
_EQUIPMENT_FREE = {"poids du corps", "autres", "body only", "other", "foam roll", ""}

_CATEGORY_OBJECTIVES: dict[str, list[str]] = {
    # Français (ETL)
    "force": ["prise_de_masse", "renforcement"],
    "cardio": ["perte_de_poids", "endurance"],
    "étirement": ["maintien", "renforcement"],
    "autres": ["renforcement", "maintien"],
    # Anglais (fallback)
    "strength": ["prise_de_masse", "renforcement"],
    "stretching": ["maintien", "renforcement"],
    "plyometrics": ["performance", "perte_de_poids"],
    "strongman": ["prise_de_masse", "performance"],
    "powerlifting": ["prise_de_masse", "performance"],
    "olympic weightlifting": ["prise_de_masse", "performance"],
    "crossfit": ["performance", "endurance", "perte_de_poids"],
}

_CATEGORY_MUSCLE_GROUP: dict[str, str] = {
    "cardio": "cardio",
    "force": "core",
    "étirement": "core",
    "strength": "core",
    "stretching": "core",
}


def _map_muscle_group(primary_muscles: list[str], category: str) -> str:
    for m in primary_muscles:
        key = m.lower().strip()
        if key in _MUSCLE_GROUP_MAP:
            return _MUSCLE_GROUP_MAP[key]
    return _CATEGORY_MUSCLE_GROUP.get(category.lower(), "core")


def _map_equipment(equipment_raw: str | None) -> list[str]:
    if not equipment_raw:
        return []
    normalized = equipment_raw.strip().lower()
    if normalized in _EQUIPMENT_FREE:
        return []
    return [equipment_raw.strip()]


def _map_exercise(item: dict[str, Any]) -> ExerciseDefinition | None:
    name = (item.get("name") or "").strip()
    if not name:
        return None

    item_id = str(item.get("id") or name.lower().replace(" ", "-"))
    level_raw = (item.get("level") or "").strip().lower()
    level = _LEVEL_MAP.get(level_raw, "intermediaire")

    primary_raw = item.get("primary_muscles")
    primary_muscles: list[str] = primary_raw if isinstance(primary_raw, list) else []

    category_raw = (item.get("category") or "").strip()
    muscle_group = _map_muscle_group(primary_muscles, category_raw)

    objectives = _CATEGORY_OBJECTIVES.get(
        category_raw.lower(), ["renforcement", "maintien"]
    )

    equipment = _map_equipment(item.get("equipment"))

    tags = [category_raw.lower()] if category_raw else []
    for m in primary_muscles[:2]:
        tags.append(m.lower())

    return ExerciseDefinition(
        id=item_id,
        name=name,
        muscle_group=muscle_group,
        level=level,
        objectives=objectives,
        equipment=equipment,
        tags=tags,
        contraindications=[],
    )


class BackendExerciseLookupService:
    """Catalogue d'exercices alimenté par le backend NestJS.

    Récupère les exercices de la table Exercise (ETL validé).
    Fallback automatique sur EXERCISE_CATALOG si le backend est indisponible.
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
        self._catalog: list[ExerciseDefinition] = []
        self._loaded_at: float = 0.0

    async def get_catalog(self) -> list[ExerciseDefinition]:
        await self._ensure_loaded()
        return self._catalog if self._catalog else list(EXERCISE_CATALOG)

    async def _ensure_loaded(self) -> None:
        if time.time() - self._loaded_at < _CACHE_TTL_SECONDS:
            return
        try:
            await self._load_from_backend()
        except Exception as exc:
            logger.warning(
                "BackendExerciseLookup: impossible de charger depuis le backend (%s)."
                " Fallback sur catalogue statique.",
                exc,
            )
            self._loaded_at = time.time() - _CACHE_TTL_SECONDS + _BACKOFF_TTL_SECONDS

    async def _load_from_backend(self) -> None:
        url = f"{self._backend_url}/exercise"
        headers = {"Authorization": f"Bearer {self._access_token}"}
        page_size = 100
        items: list[dict[str, Any]] = []

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            page = 1
            while True:
                resp = await client.get(
                    url,
                    params={"page": page, "limit": page_size},
                    headers=headers,
                )
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
                batch = resp.json()
                if not isinstance(batch, list) or not batch:
                    break
                items.extend(batch)
                if len(batch) < page_size:
                    break
                page += 1

        catalog = [ex for item in items if (ex := _map_exercise(item)) is not None]
        if not catalog:
            logger.warning(
                "BackendExerciseLookup: aucun exercice retourné, fallback statique."
            )
            return

        self._catalog = catalog
        self._loaded_at = time.time()
        logger.info(
            "BackendExerciseLookup: %d exercices chargés depuis le backend.",
            len(catalog),
        )
