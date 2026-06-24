"""Construction du jeu d'entraînement pour le modèle de scoring (EPIC #79).

Deux sources, combinées par le script d'entraînement :

1. **Échantillons réels** (`samples_from_feedback`) — reconstruits à partir des
   retours utilisateur réellement collectés (`workout_feedbacks`), des
   programmes générés (`workout_programs`) et des profils sportifs
   (`user_fitness_profiles`). Supervision faible : la note globale du
   programme (1-5) est reportée sur chaque exercice qu'il contenait, et les
   exercices explicitement signalés comme problématiques reçoivent la note
   minimale.

2. **Échantillons synthétiques** (`generate_synthetic_samples`) — utilisés en
   complément pour garantir un volume suffisant à l'entraînement et à la
   validation croisée tant que le volume réel de feedback est faible (phase
   de développement / démonstration). La note simulée combine une vérité
   terrain dérivée de la compatibilité réelle (objectif, niveau, matériel,
   contre-indications) et un bruit gaussien, pour éviter un signal trop
   parfait/non réaliste.
"""

from __future__ import annotations

import random

from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring

Sample = tuple[ExerciseDefinition, UserProfileForScoring, int]

_OBJECTIVES = [
    "perte_de_poids",
    "prise_de_masse",
    "renforcement",
    "endurance",
    "maintien",
    "performance",
]
_LEVELS = ["debutant", "intermediaire", "avance", "athlete"]
_EQUIPMENT_POOL = [
    "halteres",
    "barre",
    "banc",
    "velo",
    "rameur",
    "corde a sauter",
    "step",
    "barre de traction",
]
_PREFERENCE_POOL = ["faible impact", "intensif", "sans materiel", "cardio", "force"]
_LIMITATION_POOL = ["genou", "dos", "epaule", "coude", "poignet", None, None, None]


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _level_index(level: str) -> int:
    normalized = _normalize(level)
    return _LEVELS.index(normalized) if normalized in _LEVELS else 0


def _true_compatibility(
    exercise: ExerciseDefinition, profile: UserProfileForScoring
) -> float:
    """Vérité terrain (0-1) utilisée pour simuler une note réaliste."""
    objective_ok = (
        1.0
        if not exercise.objectives
        else float(
            _normalize(profile.objectif) in {_normalize(o) for o in exercise.objectives}
        )
    )
    level_gap = abs(_level_index(profile.niveau) - _level_index(exercise.level))
    level_ok = max(0.0, 1.0 - level_gap * 0.35)
    equipment_required = {_normalize(e) for e in exercise.equipment}
    equipment_available = {_normalize(e) for e in profile.materiel}
    equipment_ok = float(equipment_required.issubset(equipment_available))
    limitation_keys = {_normalize(item) for item in profile.limitations if item}
    contraindication_conflict = bool(
        limitation_keys.intersection(
            {_normalize(c) for c in exercise.contraindications}
        ),
    )
    limitation_ok = 0.0 if contraindication_conflict else 1.0

    return (
        0.35 * objective_ok
        + 0.25 * level_ok
        + 0.25 * equipment_ok
        + 0.15 * limitation_ok
    )


def generate_synthetic_samples(
    catalog: list[ExerciseDefinition],
    *,
    n_profiles: int = 300,
    exercises_per_profile: int = 6,
    seed: int = 42,
) -> list[Sample]:
    """Génère des triplets (exercice, profil, note simulée 1-5) bruités."""
    rng = random.Random(seed)
    samples: list[Sample] = []

    for _ in range(n_profiles):
        profile = UserProfileForScoring(
            objectif=rng.choice(_OBJECTIVES),
            niveau=rng.choice(_LEVELS),
            materiel=rng.sample(_EQUIPMENT_POOL, k=rng.randint(0, 4)),
            preferences=rng.sample(_PREFERENCE_POOL, k=rng.randint(0, 2)),
            limitations=[lim for lim in [rng.choice(_LIMITATION_POOL)] if lim],
        )
        chosen = rng.sample(catalog, k=min(exercises_per_profile, len(catalog)))
        for exercise in chosen:
            truth = _true_compatibility(exercise, profile)
            noisy = max(0.0, min(1.0, truth + rng.gauss(0, 0.12)))
            rating = max(1, min(5, round(1 + noisy * 4)))
            samples.append((exercise, profile, rating))

    return samples


def samples_from_feedback(
    feedbacks: list[dict],
    programs_by_id: dict[str, dict],
    profiles_by_user: dict[int, UserProfileForScoring],
    catalog_by_id: dict[str, ExerciseDefinition],
) -> list[Sample]:
    """Reconstruit des triplets réels à partir des collections MongoDB.

    Toutes les entrées sont des documents/dicts déjà chargés (pas d'I/O ici) —
    cette fonction est pure et testable sans MongoDB.
    """
    samples: list[Sample] = []

    for feedback in feedbacks:
        program_id = feedback.get("programId")
        program = programs_by_id.get(program_id)
        if program is None:
            continue

        profile = profiles_by_user.get(feedback.get("userId"))
        if profile is None:
            continue

        problematic = set(feedback.get("exercicesProblematiques", []))
        rating = feedback.get("rating")
        if rating is None:
            continue

        for day in program.get("programme", []):
            for planned in day.get("exercices", []):
                exercise = catalog_by_id.get(planned.get("id"))
                if exercise is None:
                    continue
                label = 1 if planned.get("id") in problematic else rating
                samples.append((exercise, profile, label))

    return samples
