"""Cas limites du planificateur hebdomadaire (niveaux élevés, rotation, fallback)."""

from app.contexts.workout.domain.data.exercises_catalog import EXERCISE_CATALOG
from app.contexts.workout.domain.services.weekly_planner import (
    _assign_groups_to_training_days,
    _exercises_per_session,
    _score_with_rotation,
    _session_duration_bounds,
    _spread_training_day_indices,
    _training_days_count,
    generate_weekly_program,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring


def _profile(niveau):
    return UserProfileForScoring(
        objectif="renforcement",
        niveau=niveau,
        materiel=[],
        preferences=[],
        limitations=[],
    )


def test_training_days_count_per_level():
    assert _training_days_count("debutant") == 3
    assert _training_days_count("intermediaire") == 4
    assert _training_days_count("avance") == 5
    assert _training_days_count("athlete") == 6


def test_session_duration_bounds_per_level():
    assert _session_duration_bounds("debutant") == (30, 45)
    assert _session_duration_bounds("intermediaire") == (45, 60)
    assert _session_duration_bounds("avance") == (60, 75)
    assert _session_duration_bounds("athlete") == (60, 90)


def test_exercises_per_session_zero_days():
    assert _exercises_per_session(0) == 3


def test_spread_indices_edge_cases():
    assert _spread_training_day_indices(0) == []
    assert _spread_training_day_indices(1) == [0]
    assert _spread_training_day_indices(7) == list(range(7))
    assert _spread_training_day_indices(8) == list(range(7))


def test_assign_groups_zero_training_days():
    assert _assign_groups_to_training_days(["jambes", "dos"], 0) == []


def test_score_with_rotation_applies_penalty_when_not_excluded():
    exercise = EXERCISE_CATALOG[0]
    full = _score_with_rotation(
        exercise, _profile("debutant"), set(), exclude_recent=False
    )
    penalised = _score_with_rotation(
        exercise, _profile("debutant"), {exercise.id}, exclude_recent=False
    )

    assert 0 < penalised < full


def test_score_with_rotation_excludes_recent():
    exercise = EXERCISE_CATALOG[0]
    assert (
        _score_with_rotation(
            exercise, _profile("debutant"), {exercise.id}, exclude_recent=True
        )
        == 0.0
    )


def test_athlete_program_has_six_training_days():
    programme = generate_weekly_program(_profile("athlete"))

    training_days = [d for d in programme if d.exercices]
    assert len(programme) == 7
    assert len(training_days) == 6


def test_program_falls_back_when_all_exercises_recent():
    """Quand tout le catalogue a été utilisé récemment, le fallback rotation s'active."""
    all_ids = [ex.id for ex in EXERCISE_CATALOG]
    programme = generate_weekly_program(
        _profile("debutant"), recent_exercise_ids=all_ids
    )

    # Le programme reste non vide grâce au fallback avec pénalité de rotation.
    assert any(d.exercices for d in programme)
