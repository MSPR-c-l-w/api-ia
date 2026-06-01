from app.models.user_profile_scoring import UserProfileForScoring
from app.services.weekly_planner import (
    _session_duration_bounds,
    _spread_training_day_indices,
    _training_days_count,
    count_muscle_group_frequency,
    generate_weekly_program,
)


def _exercise_ids(programme):
    ids = []
    for day in programme:
        ids.extend(ex.id for ex in day.exercices)
    return ids


def test_beginner_has_three_training_days_and_rest():
    profile = UserProfileForScoring(
        objectif="maintien",
        niveau="debutant",
        materiel=[],
        preferences=[],
        limitations=[],
    )
    programme = generate_weekly_program(profile)
    training_days = [d for d in programme if d.exercices]
    rest_days = [d for d in programme if not d.exercices]

    assert len(programme) == 7
    assert len(training_days) == 3
    assert len(rest_days) == 4


def test_athlete_has_five_to_six_training_days():
    profile = UserProfileForScoring(
        objectif="performance",
        niveau="athlete",
        materiel=[],
        preferences=["cardio"],
        limitations=[],
    )
    programme = generate_weekly_program(profile)
    scheduled = _spread_training_day_indices(_training_days_count(profile.niveau))
    assert 5 <= len(scheduled) <= 6
    for index in scheduled:
        assert len(programme[index].exercices) >= 1


def test_muscle_group_at_most_twice_per_week():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="intermediaire",
        materiel=["haltères", "banc", "barre"],
        preferences=[],
        limitations=[],
    )
    programme = generate_weekly_program(profile)
    frequencies = count_muscle_group_frequency(programme)
    assert all(count <= 2 for count in frequencies.values())


def test_no_duplicate_exercises_in_same_week():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="debutant",
        materiel=[],
        preferences=[],
        limitations=[],
    )
    programme = generate_weekly_program(profile)
    ids = _exercise_ids(programme)
    assert len(ids) == len(set(ids))


def test_rotation_deprioritizes_recent_exercises():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="debutant",
        materiel=[],
        preferences=[],
        limitations=[],
    )
    recent_ids = ["marche-rapide", "pont-fessier", "gainage"]
    without = set(
        _exercise_ids(generate_weekly_program(profile, recent_exercise_ids=[]))
    )
    with_recent = set(
        _exercise_ids(generate_weekly_program(profile, recent_exercise_ids=recent_ids)),
    )
    assert len(with_recent.intersection(recent_ids)) < len(
        without.intersection(recent_ids),
    )


def test_session_duration_bounds_by_level():
    assert _session_duration_bounds("debutant") == (30, 45)
    assert _session_duration_bounds("athlete") == (60, 90)
    assert _training_days_count("debutant") == 3
    assert _training_days_count("athlete") == 6
