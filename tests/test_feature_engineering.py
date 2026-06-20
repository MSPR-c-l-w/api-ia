"""Tests pour l'extraction de features du modèle de scoring appris."""

from app.contexts.workout.domain.services.feature_engineering import (
    FEATURE_NAMES,
    extract_features,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring


def _exercise(**overrides) -> ExerciseDefinition:
    defaults = {
        "id": "ex",
        "name": "Exercice",
        "muscle_group": "jambes",
        "level": "intermediaire",
        "objectives": ["renforcement"],
        "equipment": ["halteres"],
        "tags": ["force"],
        "contraindications": ["genou"],
    }
    defaults.update(overrides)
    return ExerciseDefinition(**defaults)


def _profile(**overrides) -> UserProfileForScoring:
    defaults = {
        "objectif": "renforcement",
        "niveau": "intermediaire",
        "materiel": ["halteres"],
        "preferences": ["force"],
        "limitations": [],
    }
    defaults.update(overrides)
    return UserProfileForScoring(**defaults)


def test_extract_features_returns_one_value_per_feature_name():
    features = extract_features(_exercise(), _profile())
    assert len(features) == len(FEATURE_NAMES)


def test_objective_match_is_one_when_objective_in_list():
    features = extract_features(_exercise(objectives=["renforcement"]), _profile())
    assert features[FEATURE_NAMES.index("objective_match")] == 1.0


def test_objective_match_is_zero_on_mismatch():
    features = extract_features(
        _exercise(objectives=["endurance"]),
        _profile(objectif="renforcement"),
    )
    assert features[FEATURE_NAMES.index("objective_match")] == 0.0


def test_objective_match_is_one_when_exercise_has_no_objectives():
    features = extract_features(_exercise(objectives=[]), _profile())
    assert features[FEATURE_NAMES.index("objective_match")] == 1.0


def test_level_diff_is_zero_for_matching_levels():
    features = extract_features(
        _exercise(level="intermediaire"),
        _profile(niveau="intermediaire"),
    )
    assert features[FEATURE_NAMES.index("level_diff")] == 0.0


def test_level_diff_increases_with_gap():
    features = extract_features(
        _exercise(level="athlete"),
        _profile(niveau="debutant"),
    )
    assert features[FEATURE_NAMES.index("level_diff")] == 3.0


def test_equipment_available_true_when_subset():
    features = extract_features(
        _exercise(equipment=["halteres"]),
        _profile(materiel=["halteres", "banc"]),
    )
    assert features[FEATURE_NAMES.index("equipment_available")] == 1.0


def test_equipment_available_false_when_missing():
    features = extract_features(
        _exercise(equipment=["barre"]),
        _profile(materiel=["halteres"]),
    )
    assert features[FEATURE_NAMES.index("equipment_available")] == 0.0


def test_preference_overlap_ratio_zero_when_no_preferences():
    features = extract_features(_exercise(tags=["force"]), _profile(preferences=[]))
    assert features[FEATURE_NAMES.index("preference_overlap_ratio")] == 0.0


def test_preference_overlap_ratio_full_when_all_match():
    features = extract_features(
        _exercise(tags=["force"]),
        _profile(preferences=["force"]),
    )
    assert features[FEATURE_NAMES.index("preference_overlap_ratio")] == 1.0


def test_limitation_conflict_detected():
    features = extract_features(
        _exercise(contraindications=["genou"]),
        _profile(limitations=["mal au genou"]),
    )
    assert features[FEATURE_NAMES.index("limitation_conflict")] == 1.0


def test_limitation_conflict_absent_without_overlap():
    features = extract_features(
        _exercise(contraindications=["genou"]),
        _profile(limitations=["mal au dos"]),
    )
    assert features[FEATURE_NAMES.index("limitation_conflict")] == 0.0
