from app.data.exercises_catalog import EXERCISE_CATALOG
from app.models.exercise_catalog import ExerciseDefinition
from app.models.user_profile_scoring import UserProfileForScoring
from app.services.recommendation_engine import (
    is_exercise_compatible,
    recommend_exercises,
    score_exercise,
    select_top_by_muscle_group,
)


def _find(exercise_id: str) -> ExerciseDefinition:
    return next(ex for ex in EXERCISE_CATALOG if ex.id == exercise_id)


def test_score_exercise_returns_between_zero_and_one():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="debutant",
        materiel=[],
        preferences=["faible impact"],
        limitations=[],
    )
    score = score_exercise(_find("pont-fessier"), profile)
    assert 0.0 <= score <= 1.0
    assert score > 0.5


def test_beginner_profile_prefers_accessible_exercises():
    profile = UserProfileForScoring(
        objectif="maintien",
        niveau="debutant",
        materiel=[],
        preferences=["faible impact", "sans materiel"],
        limitations=[],
    )
    selected = recommend_exercises(profile, top_n_per_group=1)
    ids = {ex.id for ex, _ in selected}
    assert "marche-rapide" in ids or "pont-fessier" in ids
    assert "burpees" not in ids or score_exercise(_find("burpees"), profile) < 0.5


def test_athlete_profile_can_select_advanced_cardio():
    profile = UserProfileForScoring(
        objectif="performance",
        niveau="athlete",
        materiel=[],
        preferences=["cardio", "intensif"],
        limitations=[],
    )
    score_burpees = score_exercise(_find("burpees"), profile)
    score_marche = score_exercise(_find("marche-rapide"), profile)
    assert score_burpees > score_marche


def test_exercise_blocked_by_temporary_limitation_token():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="debutant",
        limitations=["exercice_problematique:squat-pdc"],
    )
    assert not is_exercise_compatible(_find("squat-pdc"), profile)


def test_knee_injury_excludes_squats_and_lunges():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="intermediaire",
        materiel=[],
        preferences=[],
        limitations=["mal au genou"],
    )
    assert score_exercise(_find("squat-pdc"), profile) == 0.0
    assert score_exercise(_find("fentes"), profile) == 0.0
    assert not is_exercise_compatible(_find("squat-pdc"), profile)
    selected_ids = {ex.id for ex, _ in recommend_exercises(profile)}
    assert "squat-pdc" not in selected_ids
    assert "fentes" not in selected_ids


def test_missing_equipment_excludes_exercise():
    profile = UserProfileForScoring(
        objectif="prise_de_masse",
        niveau="intermediaire",
        materiel=[],
        preferences=[],
        limitations=[],
    )
    bench_press = _find("developpe-couche-halteres")
    assert score_exercise(bench_press, profile) == 0.0


def test_equipment_available_allows_exercise():
    profile = UserProfileForScoring(
        objectif="prise_de_masse",
        niveau="intermediaire",
        materiel=["haltères", "banc"],
        preferences=[],
        limitations=[],
    )
    bench_press = _find("developpe-couche-halteres")
    assert score_exercise(bench_press, profile) > 0.0


def test_select_top_n_per_muscle_group():
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="debutant",
        materiel=[],
        preferences=[],
        limitations=[],
    )
    selected = select_top_by_muscle_group(
        EXERCISE_CATALOG,
        profile,
        top_n=1,
        catalog=EXERCISE_CATALOG,
    )
    groups = [ex.muscle_group for ex, _ in selected]
    assert len(groups) == len(set(groups))
