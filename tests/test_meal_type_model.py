"""Tests pour MealTypeModel : entraînement, prédiction, persistance."""

import numpy as np
import pytest

from app.contexts.nutrition.domain.meal_type_model import (
    VALID_MEAL_TYPES,
    MealTypeModel,
)


def _synthetic_dataset(n_per_class: int = 20) -> tuple[np.ndarray, list[str]]:
    """Petit dataset synthétique séparable, juste pour tester la mécanique
    d'entraînement/prédiction (la qualité du modèle réel est évaluée par
    scripts/train_meal_type_model.py sur les vraies données Kaggle)."""
    rng = np.random.RandomState(0)
    x_parts = []
    y_parts = []
    # Chaque classe est centrée sur une zone distincte de l'espace de features.
    for i, label in enumerate(VALID_MEAL_TYPES):
        base = np.full((n_per_class, 8), float(i * 100))
        noise = rng.normal(0, 1, size=(n_per_class, 8))
        x_parts.append(base + noise)
        y_parts.extend([label] * n_per_class)
    return np.vstack(x_parts), y_parts


@pytest.fixture()
def trained_model() -> MealTypeModel:
    x, y = _synthetic_dataset()
    return MealTypeModel(learning_rate=0.1).fit(x, y)


def test_predict_before_fit_raises():
    model = MealTypeModel()
    with pytest.raises(RuntimeError):
        model.predict(np.zeros((1, 8)))


def test_predict_proba_before_fit_raises():
    model = MealTypeModel()
    with pytest.raises(RuntimeError):
        model.predict_proba(np.zeros((1, 8)))


def test_predict_returns_valid_meal_type(trained_model):
    x, _ = _synthetic_dataset(n_per_class=1)
    predictions = trained_model.predict(x)
    assert all(label in VALID_MEAL_TYPES for label in predictions)


def test_predict_meal_type_on_separable_data_is_accurate(trained_model):
    item = {
        "calories_kcal": 300.0,
        "protein_g": 300.0,
        "carbohydrates_g": 300.0,
        "fat_g": 300.0,
        "fiber_g": 300.0,
        "sugar_g": 300.0,
        "sodium_mg": 300.0,
        "cholesterol_mg": 300.0,
    }
    assert trained_model.predict_meal_type(item) == VALID_MEAL_TYPES[3]


def test_feature_importances_sum_to_about_one(trained_model):
    importances = trained_model.feature_importances()
    assert abs(sum(importances.values()) - 1.0) < 1e-6


def test_save_and_load_roundtrip(trained_model, tmp_path):
    path = tmp_path / "model.joblib"
    trained_model.save(path)

    reloaded = MealTypeModel.load(path)

    assert reloaded is not None
    x, _ = _synthetic_dataset(n_per_class=1)
    assert list(trained_model.predict(x)) == list(reloaded.predict(x))


def test_load_returns_none_when_file_missing(tmp_path):
    missing_path = tmp_path / "does-not-exist.joblib"
    assert MealTypeModel.load(missing_path) is None


def test_save_before_fit_raises(tmp_path):
    model = MealTypeModel()
    with pytest.raises(RuntimeError):
        model.save(tmp_path / "model.joblib")


def test_feature_importances_before_fit_raises():
    model = MealTypeModel()
    with pytest.raises(RuntimeError):
        model.feature_importances()
