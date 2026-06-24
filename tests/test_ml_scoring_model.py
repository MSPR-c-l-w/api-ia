"""Tests pour ExerciseScoringModel : entraînement, prédiction, persistance."""

import numpy as np
import pytest

from app.contexts.workout.domain.services.dataset_builder import (
    generate_synthetic_samples,
)
from app.contexts.workout.domain.services.ml_scoring_model import (
    ExerciseScoringModel,
    samples_to_xy,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)


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


@pytest.fixture()
def trained_model() -> ExerciseScoringModel:
    samples = generate_synthetic_samples(
        _catalog(),
        n_profiles=60,
        exercises_per_profile=2,
        seed=3,
    )
    x, y = samples_to_xy(samples)
    return ExerciseScoringModel(learning_rate=0.1).fit(x, y)


def test_samples_to_xy_label_is_binary():
    samples = [(_catalog()[0], _catalog_profile(), rating) for rating in [1, 3, 4, 5]]
    _, y = samples_to_xy(samples)
    assert set(y.tolist()) <= {0, 1}


def _catalog_profile():
    from app.contexts.workout.domain.value_objects.user_profile import (
        UserProfileForScoring,
    )

    return UserProfileForScoring(
        objectif="renforcement",
        niveau="intermediaire",
        materiel=[],
        preferences=[],
        limitations=[],
    )


def test_predict_before_fit_raises():
    model = ExerciseScoringModel()
    with pytest.raises(RuntimeError):
        model.predict(np.zeros((1, 7)))


def test_score_exercise_returns_value_between_zero_and_one(trained_model):
    exercise, profile, _ = generate_synthetic_samples(
        _catalog(),
        n_profiles=1,
        exercises_per_profile=1,
        seed=5,
    )[0]
    score = trained_model.score_exercise(exercise, profile)
    assert 0.0 <= score <= 1.0


def test_feature_importances_sum_to_about_one(trained_model):
    importances = trained_model.feature_importances()
    assert abs(sum(importances.values()) - 1.0) < 1e-6


def test_save_and_load_roundtrip(trained_model, tmp_path):
    path = tmp_path / "model.joblib"
    trained_model.save(path)

    reloaded = ExerciseScoringModel.load(path)

    assert reloaded is not None
    exercise, profile, _ = generate_synthetic_samples(
        _catalog(),
        n_profiles=1,
        exercises_per_profile=1,
        seed=11,
    )[0]
    assert trained_model.score_exercise(exercise, profile) == pytest.approx(
        reloaded.score_exercise(exercise, profile),
    )


def test_load_returns_none_when_file_missing(tmp_path):
    missing_path = tmp_path / "does-not-exist.joblib"
    assert ExerciseScoringModel.load(missing_path) is None
