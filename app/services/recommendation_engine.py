"""Moteur multi-critères de sélection d'exercices — EPIC #79 #95."""

from app.data.exercises_catalog import LEVEL_ORDER, EXERCISE_CATALOG
from app.models.exercise_catalog import ExerciseDefinition
from app.models.user_profile_scoring import UserProfileForScoring

WEIGHT_OBJECTIVE = 0.40
WEIGHT_LEVEL = 0.25
WEIGHT_EQUIPMENT = 0.20
WEIGHT_PREFERENCES = 0.10
WEIGHT_LIMITATIONS = 0.05

LIMITATION_KEYWORDS: dict[str, list[str]] = {
    "genou": ["genou", "knee", "rotule"],
    "dos": ["dos", "lombaire", "back"],
    "epaule": ["epaule", "shoulder"],
}


def _normalize(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _extract_limitation_keys(limitations: list[str]) -> set[str]:
    keys: set[str] = set()
    for item in limitations:
        text = _normalize(item)
        for key, keywords in LIMITATION_KEYWORDS.items():
            if any(kw in text for kw in keywords):
                keys.add(key)
    return keys


def _level_index(level: str) -> int:
    normalized = _normalize(level)
    if normalized in LEVEL_ORDER:
        return LEVEL_ORDER.index(normalized)
    return 0


def _score_objective(exercise: ExerciseDefinition, profile: UserProfileForScoring) -> float:
    objective = _normalize(profile.objectif)
    if not exercise.objectives:
        return 0.5
    if objective in {_normalize(o) for o in exercise.objectives}:
        return 1.0
    return 0.25


def _score_level(exercise: ExerciseDefinition, profile: UserProfileForScoring) -> float:
    user_idx = _level_index(profile.niveau)
    ex_idx = _level_index(exercise.level)
    diff = abs(user_idx - ex_idx)
    if diff == 0:
        return 1.0
    if diff == 1:
        return 0.6
    return 0.2


def _score_equipment_availability(
    exercise: ExerciseDefinition,
    profile: UserProfileForScoring,
) -> float:
    if not exercise.equipment:
        return 1.0
    user_equipment = {_normalize(e) for e in profile.materiel}
    required = {_normalize(e) for e in exercise.equipment}
    if required.issubset(user_equipment):
        return 1.0
    return 0.0


def _score_preferences(exercise: ExerciseDefinition, profile: UserProfileForScoring) -> float:
    if not profile.preferences:
        return 0.5
    exercise_tags = {_normalize(t) for t in exercise.tags}
    prefs = {_normalize(p) for p in profile.preferences}
    overlap = exercise_tags.intersection(prefs)
    if overlap:
        return min(1.0, len(overlap) / len(prefs) + 0.5)
    return 0.2


def _score_limitations_soft(
    exercise: ExerciseDefinition,
    profile: UserProfileForScoring,
) -> float:
    user_limits = _extract_limitation_keys(profile.limitations)
    if not user_limits:
        return 1.0
    if not exercise.contraindications:
        return 1.0
    conflict = user_limits.intersection(set(exercise.contraindications))
    return 0.0 if conflict else 1.0


def _blocked_exercise_ids(limitations: list[str]) -> set[str]:
    prefix = "exercice_problematique:"
    return {
        item.removeprefix(prefix)
        for item in limitations
        if item.startswith(prefix)
    }


def is_exercise_compatible(
    exercise: ExerciseDefinition,
    profile: UserProfileForScoring,
) -> bool:
    """Filtres durs : limitations et matériel indisponible."""
    if exercise.id in _blocked_exercise_ids(profile.limitations):
        return False
    if _score_limitations_soft(exercise, profile) == 0.0:
        return False
    if _score_equipment_availability(exercise, profile) == 0.0:
        return False
    return True


def score_exercise(
    exercise: ExerciseDefinition,
    user_profile: UserProfileForScoring,
) -> float:
    """
    Score entre 0 et 1 selon objectif (40 %), niveau (25 %), matériel (20 %),
    préférences (10 %), limitations (5 %).
  """
    if not is_exercise_compatible(exercise, user_profile):
        return 0.0

    equipment_score = _score_equipment_availability(exercise, user_profile)
    total = (
        WEIGHT_OBJECTIVE * _score_objective(exercise, user_profile)
        + WEIGHT_LEVEL * _score_level(exercise, user_profile)
        + WEIGHT_EQUIPMENT * equipment_score
        + WEIGHT_PREFERENCES * _score_preferences(exercise, user_profile)
        + WEIGHT_LIMITATIONS * _score_limitations_soft(exercise, user_profile)
    )
    return round(min(1.0, max(0.0, total)), 4)


def select_top_by_muscle_group(
    exercises: list[ExerciseDefinition],
    user_profile: UserProfileForScoring,
    *,
    top_n: int = 2,
    catalog: list[ExerciseDefinition] | None = None,
) -> list[tuple[ExerciseDefinition, float]]:
    """
    Sélectionne les top N exercices par groupe musculaire selon le score.
    """
    pool = catalog if catalog is not None else exercises
    scored: list[tuple[ExerciseDefinition, float]] = []

    for exercise in pool:
        score = score_exercise(exercise, user_profile)
        if score > 0:
            scored.append((exercise, score))

    by_group: dict[str, list[tuple[ExerciseDefinition, float]]] = {}
    for exercise, score in scored:
        by_group.setdefault(exercise.muscle_group, []).append((exercise, score))

    selected: list[tuple[ExerciseDefinition, float]] = []
    for group in sorted(by_group.keys()):
        ranked = sorted(by_group[group], key=lambda item: item[1], reverse=True)
        selected.extend(ranked[:top_n])

    return sorted(selected, key=lambda item: item[1], reverse=True)


def recommend_exercises(
    user_profile: UserProfileForScoring,
    *,
    top_n_per_group: int = 2,
) -> list[tuple[ExerciseDefinition, float]]:
    """Point d'entrée : catalogue complet + sélection équilibrée."""
    return select_top_by_muscle_group(
        EXERCISE_CATALOG,
        user_profile,
        top_n=top_n_per_group,
        catalog=EXERCISE_CATALOG,
    )
