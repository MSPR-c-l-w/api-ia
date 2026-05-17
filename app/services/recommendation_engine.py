"""Compatibilité — moteur de scoring dans le domaine workout."""

from app.contexts.workout.domain.services.recommendation_engine import (
    LIMITATION_KEYWORDS,
    WEIGHT_EQUIPMENT,
    WEIGHT_LEVEL,
    WEIGHT_LIMITATIONS,
    WEIGHT_OBJECTIVE,
    WEIGHT_PREFERENCES,
    is_exercise_compatible,
    recommend_exercises,
    score_exercise,
    select_top_by_muscle_group,
)

__all__ = [
    "LIMITATION_KEYWORDS",
    "WEIGHT_EQUIPMENT",
    "WEIGHT_LEVEL",
    "WEIGHT_LIMITATIONS",
    "WEIGHT_OBJECTIVE",
    "WEIGHT_PREFERENCES",
    "is_exercise_compatible",
    "recommend_exercises",
    "score_exercise",
    "select_top_by_muscle_group",
]
