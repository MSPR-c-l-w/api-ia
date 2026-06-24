"""Extraction de features pour le modèle de scoring appris (EPIC #79).

Réutilise les mêmes signaux que l'heuristique historique (``recommendation_engine``)
mais les expose comme un vecteur de features plutôt que comme une formule à poids
fixes : c'est au modèle d'apprendre la pondération optimale à partir des retours
utilisateur, au lieu de poids choisis arbitrairement (0.40 / 0.25 / 0.20 / 0.10 / 0.05).
"""

from __future__ import annotations

from app.contexts.workout.domain.data.exercises_catalog import LEVEL_ORDER
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring

FEATURE_NAMES: list[str] = [
    "objective_match",
    "level_diff",
    "equipment_available",
    "preference_overlap_ratio",
    "limitation_conflict",
    "n_contraindications",
    "n_equipment_required",
]


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _level_index(level: str) -> int:
    normalized = _normalize(level)
    if normalized in LEVEL_ORDER:
        return LEVEL_ORDER.index(normalized)
    return 0


_LIMITATION_KEYWORDS: dict[str, list[str]] = {
    "genou": ["genou", "knee", "rotule"],
    "dos": ["dos", "lombaire", "back"],
    "epaule": ["epaule", "shoulder"],
}


def _extract_limitation_keys(limitations: list[str]) -> set[str]:
    keys: set[str] = set()
    for item in limitations:
        text = _normalize(item)
        for key, keywords in _LIMITATION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                keys.add(key)
    return keys


def extract_features(
    exercise: ExerciseDefinition,
    profile: UserProfileForScoring,
) -> list[float]:
    """Vecteur de features numériques, ordre = ``FEATURE_NAMES``."""
    objective = _normalize(profile.objectif)
    objective_match = (
        1.0
        if not exercise.objectives
        else (1.0 if objective in {_normalize(o) for o in exercise.objectives} else 0.0)
    )

    level_diff = float(abs(_level_index(profile.niveau) - _level_index(exercise.level)))

    user_equipment = {_normalize(e) for e in profile.materiel}
    required_equipment = {_normalize(e) for e in exercise.equipment}
    equipment_available = 1.0 if required_equipment.issubset(user_equipment) else 0.0

    exercise_tags = {_normalize(t) for t in exercise.tags}
    prefs = {_normalize(p) for p in profile.preferences}
    preference_overlap_ratio = (
        len(exercise_tags.intersection(prefs)) / len(prefs) if prefs else 0.0
    )

    user_limits = _extract_limitation_keys(profile.limitations)
    limitation_conflict = (
        1.0 if user_limits.intersection(set(exercise.contraindications)) else 0.0
    )

    return [
        objective_match,
        level_diff,
        equipment_available,
        preference_overlap_ratio,
        limitation_conflict,
        float(len(exercise.contraindications)),
        float(len(exercise.equipment)),
    ]
