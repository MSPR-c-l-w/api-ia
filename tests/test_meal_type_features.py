"""Tests pour l'extraction de features du modèle de type de repas."""

from app.contexts.nutrition.domain.meal_type_features import (
    FEATURE_NAMES,
    extract_features,
)


def _item(**overrides) -> dict:
    defaults = {
        "calories_kcal": 350,
        "protein_g": 5,
        "carbohydrates_g": 60,
        "fat_g": 12,
        "fiber_g": 10,
        "sugar_g": 30,
        "sodium_mg": 40,
        "cholesterol_mg": 0,
    }
    defaults.update(overrides)
    return defaults


def test_extract_features_returns_one_value_per_feature_name():
    features = extract_features(_item())
    assert len(features) == len(FEATURE_NAMES)


def test_extract_features_preserves_values_in_declared_order():
    features = extract_features(_item())
    assert features == [350.0, 5.0, 60.0, 12.0, 10.0, 30.0, 40.0, 0.0]


def test_extract_features_defaults_missing_fields_to_zero():
    features = extract_features({"calories_kcal": 200})
    assert features == [200.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_extract_features_handles_none_values():
    features = extract_features(_item(sodium_mg=None, cholesterol_mg=None))
    assert features[FEATURE_NAMES.index("sodium_mg")] == 0.0
    assert features[FEATURE_NAMES.index("cholesterol_mg")] == 0.0
