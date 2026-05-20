"""Métriques d'évaluation du moteur de recommandations (MSE, RMSE, RSS, TSS, R²)."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_squared_error, r2_score

from app.contexts.workout.domain.value_objects.exercise_definition import ExerciseDefinition
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring
from app.contexts.workout.domain.services.recommendation_engine import score_exercise


def _normalize_rating(rating: int, min_r: int = 1, max_r: int = 5) -> float:
    """Ramène une note utilisateur (1-5) dans [0, 1]."""
    return (rating - min_r) / (max_r - min_r)


def compute_engine_metrics(
    samples: list[tuple[ExerciseDefinition, UserProfileForScoring, int]],
) -> dict[str, float]:
    """
    Calcule MSE, RMSE, RSS, TSS et R² à partir de paires (exercice, profil, note_réelle).

    Paramètres
    ----------
    samples :
        Liste de (ExerciseDefinition, UserProfileForScoring, rating).
        ``rating`` est une note entière entre 1 et 5.

    Retourne
    --------
    dict contenant : mse, rmse, rss, tss, r2
    """
    if not samples:
        raise ValueError("La liste de samples ne peut pas être vide.")

    y_pred = np.array(
        [score_exercise(ex, profile) for ex, profile, _ in samples],
        dtype=float,
    )
    y_true = np.array(
        [_normalize_rating(rating) for _, _, rating in samples],
        dtype=float,
    )

    mse: float = float(mean_squared_error(y_true, y_pred))
    rmse: float = float(np.sqrt(mse))
    rss: float = float(np.sum((y_true - y_pred) ** 2))
    tss: float = float(np.sum((y_true - y_true.mean()) ** 2))
    r2: float = float(r2_score(y_true, y_pred))

    return {
        "mse": round(mse, 6),
        "rmse": round(rmse, 6),
        "rss": round(rss, 6),
        "tss": round(tss, 6),
        "r2": round(r2, 6),
        "n_samples": len(samples),
    }
