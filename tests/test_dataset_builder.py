"""Tests pour la construction du dataset d'entraînement (réel + synthétique)."""

from app.contexts.workout.domain.services.dataset_builder import (
    generate_synthetic_samples,
    samples_from_feedback,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring


def _catalog() -> list[ExerciseDefinition]:
    return [
        ExerciseDefinition(
            id="squat",
            name="Squat",
            muscle_group="jambes",
            level="intermediaire",
            objectives=["renforcement"],
            equipment=["halteres"],
            tags=["force"],
            contraindications=["genou"],
        ),
        ExerciseDefinition(
            id="course",
            name="Course",
            muscle_group="cardio",
            level="debutant",
            objectives=["endurance"],
            equipment=[],
            tags=["cardio"],
            contraindications=[],
        ),
    ]


def test_generate_synthetic_samples_returns_expected_volume():
    samples = generate_synthetic_samples(
        _catalog(),
        n_profiles=10,
        exercises_per_profile=2,
        seed=1,
    )
    assert len(samples) == 20


def test_generate_synthetic_samples_ratings_within_bounds():
    samples = generate_synthetic_samples(
        _catalog(),
        n_profiles=20,
        exercises_per_profile=2,
        seed=7,
    )
    ratings = [rating for _, _, rating in samples]
    assert all(1 <= r <= 5 for r in ratings)


def test_generate_synthetic_samples_is_deterministic_with_seed():
    a = generate_synthetic_samples(
        _catalog(), n_profiles=5, exercises_per_profile=2, seed=99
    )
    b = generate_synthetic_samples(
        _catalog(), n_profiles=5, exercises_per_profile=2, seed=99
    )
    assert [r for _, _, r in a] == [r for _, _, r in b]


def test_samples_from_feedback_reports_program_rating_on_each_exercise():
    catalog_by_id = {ex.id: ex for ex in _catalog()}
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="intermediaire",
        materiel=["halteres"],
        preferences=[],
        limitations=[],
    )
    programs_by_id = {
        "prog1": {
            "programme": [
                {"jour": "lundi", "exercices": [{"id": "squat"}, {"id": "course"}]},
            ],
        },
    }
    feedbacks = [
        {"programId": "prog1", "userId": 1, "rating": 5, "exercicesProblematiques": []}
    ]

    samples = samples_from_feedback(
        feedbacks,
        programs_by_id,
        {1: profile},
        catalog_by_id,
    )

    assert len(samples) == 2
    assert all(rating == 5 for _, _, rating in samples)


def test_samples_from_feedback_marks_problematic_exercise_as_negative():
    catalog_by_id = {ex.id: ex for ex in _catalog()}
    profile = UserProfileForScoring(
        objectif="renforcement",
        niveau="intermediaire",
        materiel=["halteres"],
        preferences=[],
        limitations=[],
    )
    programs_by_id = {
        "prog1": {
            "programme": [{"jour": "lundi", "exercices": [{"id": "squat"}]}],
        },
    }
    feedbacks = [
        {
            "programId": "prog1",
            "userId": 1,
            "rating": 5,
            "exercicesProblematiques": ["squat"],
        },
    ]

    samples = samples_from_feedback(
        feedbacks,
        programs_by_id,
        {1: profile},
        catalog_by_id,
    )

    assert samples == [(catalog_by_id["squat"], profile, 1)]


def test_samples_from_feedback_skips_unknown_program():
    samples = samples_from_feedback(
        [
            {
                "programId": "missing",
                "userId": 1,
                "rating": 4,
                "exercicesProblematiques": [],
            }
        ],
        {},
        {},
        {},
    )
    assert samples == []


def test_samples_from_feedback_skips_unknown_profile():
    programs_by_id = {
        "prog1": {"programme": [{"jour": "lundi", "exercices": [{"id": "squat"}]}]},
    }
    samples = samples_from_feedback(
        [
            {
                "programId": "prog1",
                "userId": 999,
                "rating": 4,
                "exercicesProblematiques": [],
            }
        ],
        programs_by_id,
        {},
        {ex.id: ex for ex in _catalog()},
    )
    assert samples == []
