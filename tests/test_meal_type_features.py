"""Tests pour l'extraction de features du modèle de type de repas."""

import pytest

from app.contexts.nutrition.domain import meal_type_features as mtf


@pytest.fixture(autouse=True)
def _fixed_categories(tmp_path):
    """Catégories de test contrôlées, indépendantes du fichier JSON généré
    par l'entraînement réel — les tests doivent rester déterministes même si
    le catalogue Nutrition change. Réinitialisées avant chaque test."""
    mtf.set_known_categories(["Fruits", "Desserts"], path=tmp_path / "categories.json")


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


def _macros(features: list[float]) -> list[float]:
    return features[:8]


def test_extract_features_returns_one_value_per_feature_name():
    features = mtf.extract_features(_item())
    assert len(features) == len(mtf.FEATURE_NAMES)


def test_extract_features_preserves_macro_values_in_declared_order():
    features = mtf.extract_features(_item())
    assert _macros(features) == [350.0, 5.0, 60.0, 12.0, 10.0, 30.0, 40.0, 0.0]


def test_extract_features_defaults_missing_macro_fields_to_zero():
    features = mtf.extract_features({"calories_kcal": 200})
    assert _macros(features) == [200.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_extract_features_handles_none_values():
    features = mtf.extract_features(_item(sodium_mg=None, cholesterol_mg=None))
    assert features[mtf.FEATURE_NAMES.index("sodium_mg")] == 0.0
    assert features[mtf.FEATURE_NAMES.index("cholesterol_mg")] == 0.0


def test_extract_features_one_hot_encodes_known_category():
    features = mtf.extract_features(_item(category="Fruits"))
    assert features[mtf.FEATURE_NAMES.index("category_Fruits")] == 1.0
    assert features[mtf.FEATURE_NAMES.index("category_autre")] == 0.0
    assert sum(features[8:]) == 1.0


def test_extract_features_falls_back_to_autre_for_unknown_category():
    features = mtf.extract_features(_item(category="Catégorie jamais vue"))
    assert features[mtf.FEATURE_NAMES.index("category_autre")] == 1.0
    assert sum(features[8:]) == 1.0


def test_extract_features_falls_back_to_autre_when_category_missing():
    # Cas réel de meal_composer.py : le catalogue ne propage pas la catégorie.
    features = mtf.extract_features(_item())
    assert features[mtf.FEATURE_NAMES.index("category_autre")] == 1.0
    assert sum(features[8:]) == 1.0


def test_set_known_categories_persists_to_disk(tmp_path):
    path = tmp_path / "categories.json"
    mtf.set_known_categories(["Légume", "Légume", "Fruits", None, ""], path=path)

    assert mtf._KNOWN_CATEGORIES == ["Fruits", "Légume"]
    assert mtf.load_known_categories(path) == ["Fruits", "Légume"]


def test_load_known_categories_returns_empty_list_when_file_missing(tmp_path):
    assert mtf.load_known_categories(tmp_path / "absent.json") == []
