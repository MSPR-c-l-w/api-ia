"""Compatibilité — planificateur hebdomadaire dans le domaine workout."""

from app.contexts.workout.domain.services.weekly_planner import (
    MAX_EXERCISES_PER_SESSION,
    MAX_GROUP_FREQUENCY_PER_WEEK,
    ROTATION_PENALTY,
    WEEK_DAYS,
    _assign_groups_to_training_days,
    _exercises_per_session,
    _ranked_exercises,
    _score_with_rotation,
    _session_duration_bounds,
    _spread_training_day_indices,
    _to_planned_exercise,
    _training_days_count,
    count_muscle_group_frequency,
    generate_weekly_program,
)

__all__ = [
    "MAX_EXERCISES_PER_SESSION",
    "MAX_GROUP_FREQUENCY_PER_WEEK",
    "ROTATION_PENALTY",
    "WEEK_DAYS",
    "_assign_groups_to_training_days",
    "_exercises_per_session",
    "_ranked_exercises",
    "_score_with_rotation",
    "_session_duration_bounds",
    "_spread_training_day_indices",
    "_to_planned_exercise",
    "_training_days_count",
    "count_muscle_group_frequency",
    "generate_weekly_program",
]
