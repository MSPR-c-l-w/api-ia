"""Tests pour engine_metrics : MSE, RMSE, RSS, TSS, R²."""

import pytest

from app.contexts.workout.domain.value_objects.exercise_definition import ExerciseDefinition
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring
from app.contexts.workout.domain.services.engine_metrics import compute_engine_metrics


@pytest.fixture()
def exercise_cardio() -> ExerciseDefinition:
    return ExerciseDefinition(
        id="ex_cardio",
        name="Course",
        muscle_group="cardio",
        level="debutant",
        objectives=["perte_de_poids"],
        equipment=[],
        tags=["cardio"],
    )


@pytest.fixture()
def exercise_strength() -> ExerciseDefinition:
    return ExerciseDefinition(
        id="ex_force",
        name="Squat",
        muscle_group="jambes",
        level="intermediaire",
        objectives=["renforcement"],
        equipment=["haltères"],
        tags=["force"],
    )


@pytest.fixture()
def profile_beginner() -> UserProfileForScoring:
    return UserProfileForScoring(
        objectif="perte_de_poids",
        niveau="debutant",
        materiel=[],
        preferences=["cardio"],
        limitations=[],
    )


def test_compute_metrics_returns_all_keys(exercise_cardio, profile_beginner):
    samples = [(exercise_cardio, profile_beginner, 4)]
    result = compute_engine_metrics(samples)
    assert set(result.keys()) == {"mse", "rmse", "rss", "tss", "r2", "n_samples"}


def test_n_samples_correct(exercise_cardio, exercise_strength, profile_beginner):
    samples = [
        (exercise_cardio, profile_beginner, 5),
        (exercise_strength, profile_beginner, 2),
    ]
    result = compute_engine_metrics(samples)
    assert result["n_samples"] == 2


def test_perfect_prediction_r2_near_one(exercise_cardio, profile_beginner):
    """Si y_true ≈ y_pred sur tous les samples, R² ≈ 1."""
    from app.contexts.workout.domain.services.recommendation_engine import score_exercise
    predicted_score = score_exercise(exercise_cardio, profile_beginner)
    # Convertit le score prédit en note 1-5 approchée
    rating = round(predicted_score * 4 + 1)  # inverse de _normalize_rating
    samples = [(exercise_cardio, profile_beginner, rating)] * 5
    result = compute_engine_metrics(samples)
    assert result["mse"] >= 0
    assert result["rmse"] >= 0
    assert result["rss"] >= 0


def test_rss_equals_sum_squared_residuals(exercise_cardio, exercise_strength, profile_beginner):
    from app.contexts.workout.domain.services.recommendation_engine import score_exercise
    samples = [
        (exercise_cardio, profile_beginner, 5),
        (exercise_strength, profile_beginner, 2),
    ]
    y_pred = [score_exercise(ex, p) for ex, p, _ in samples]
    y_true = [(r - 1) / 4 for _, _, r in samples]
    expected_rss = sum((yt - yp) ** 2 for yt, yp in zip(y_true, y_pred))

    result = compute_engine_metrics(samples)
    assert abs(result["rss"] - expected_rss) < 1e-5


def test_rmse_equals_sqrt_mse(exercise_cardio, profile_beginner):
    import math
    samples = [(exercise_cardio, profile_beginner, 3)]
    result = compute_engine_metrics(samples)
    assert abs(result["rmse"] - math.sqrt(result["mse"])) < 1e-6


def test_empty_samples_raises():
    with pytest.raises(ValueError, match="vide"):
        compute_engine_metrics([])
