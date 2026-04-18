"""
Inference module: biometrics → nutritional targets → scored meal recommendations.
"""

import os
from typing import Any

import joblib
import numpy as np

from app.ml.train import (
    ACTIVITY_LEVELS,
    MEAL_TYPES,
    MODEL_PATH,
    train_and_save_model,
)

_model = None


def _get_model():
    global _model
    if _model is None:
        if not os.path.exists(MODEL_PATH):
            _model = train_and_save_model(MODEL_PATH)
        else:
            _model = joblib.load(MODEL_PATH)
    return _model


def predict_nutritional_targets(
    age: int,
    weight_kg: float,
    height_cm: float,
    gender: str,
    physical_activity_level: str,
    meal_type: str,
    bmi: float | None = None,
) -> dict[str, float]:
    """
    Predict the optimal nutritional targets for a single meal given user biometrics.

    Returns a dict with keys:
        target_calories, target_protein_g, target_carbs_g, target_fat_g
    """
    if bmi is None:
        bmi = weight_kg / (height_cm / 100) ** 2

    gender_num = 1 if gender.lower() == "male" else 0

    activity_num = (
        ACTIVITY_LEVELS.index(physical_activity_level)
        if physical_activity_level in ACTIVITY_LEVELS
        else 2  # default: moderately_active
    )

    meal_type_num = (
        MEAL_TYPES.index(meal_type) if meal_type in MEAL_TYPES else 1  # default: lunch
    )

    X = np.array([[age, weight_kg, height_cm, bmi, gender_num, activity_num, meal_type_num]])

    predictions = _get_model().predict(X)[0]

    return {
        "target_calories": round(float(predictions[0]), 1),
        "target_protein_g": round(float(predictions[1]), 1),
        "target_carbs_g": round(float(predictions[2]), 1),
        "target_fat_g": round(float(predictions[3]), 1),
    }


# Constraint thresholds
_CONSTRAINT_RULES: dict[str, dict[str, Any]] = {
    "low_carb": {"field": "carbohydrates_g", "op": "gt", "threshold": 30, "penalty": 0.5},
    "high_protein": {"field": "protein_g", "op": "lt", "threshold": 25, "penalty": 0.3},
    "low_fat": {"field": "fat_g", "op": "gt", "threshold": 15, "penalty": 0.3},
    "low_sodium": {"field": "sodium_mg", "op": "gt", "threshold": 500, "penalty": 0.2},
    "low_sugar": {"field": "sugar_g", "op": "gt", "threshold": 10, "penalty": 0.2},
}

_MEAT_KEYWORDS = {"chicken", "beef", "pork", "meat", "fish", "seafood", "turkey", "lamb"}


def _apply_constraints(
    meal: dict[str, Any], dietary_constraints: list[str]
) -> tuple[float, list[str]]:
    """Return (penalty, list_of_violations)."""
    penalty = 0.0
    violations: list[str] = []

    for constraint in dietary_constraints:
        rule = _CONSTRAINT_RULES.get(constraint)
        if rule:
            value = float(meal.get(rule["field"]) or 0)
            breached = (rule["op"] == "gt" and value > rule["threshold"]) or (
                rule["op"] == "lt" and value < rule["threshold"]
            )
            if breached:
                penalty += rule["penalty"]
                violations.append(f"{rule['field']}_{rule['op']}_{rule['threshold']}")

        if constraint in {"vegetarian", "vegan"}:
            category = (meal.get("category") or "").lower()
            name = (meal.get("name") or "").lower()
            if any(kw in category or kw in name for kw in _MEAT_KEYWORDS):
                penalty += 1.0
                violations.append("contains_meat")

    return penalty, violations


def score_and_rank_meals(
    meals: list[dict[str, Any]],
    targets: dict[str, float],
    dietary_constraints: list[str] | None = None,
    top_n: int = 5,
) -> list[dict[str, Any]]:
    """
    Score each meal against predicted nutritional targets and return the top N.

    Scoring: weighted normalised Euclidean distance (lower = better match).
    Weights: calories 40%, protein 25%, carbs 20%, fat 15%.
    """
    if dietary_constraints is None:
        dietary_constraints = []

    t_cal = targets["target_calories"]
    t_pro = targets["target_protein_g"]
    t_car = targets["target_carbs_g"]
    t_fat = targets["target_fat_g"]

    scored: list[dict[str, Any]] = []

    for meal in meals:
        cal = float(meal.get("calories_kcal") or meal.get("calories") or 0)
        pro = float(meal.get("protein_g") or 0)
        car = float(meal.get("carbohydrates_g") or 0)
        fat = float(meal.get("fat_g") or 0)

        # Normalised component differences
        cal_diff = abs(cal - t_cal) / max(t_cal, 1)
        pro_diff = abs(pro - t_pro) / max(t_pro, 1)
        car_diff = abs(car - t_car) / max(t_car, 1)
        fat_diff = abs(fat - t_fat) / max(t_fat, 1)

        distance = 0.40 * cal_diff + 0.25 * pro_diff + 0.20 * car_diff + 0.15 * fat_diff

        penalty, violations = _apply_constraints(meal, dietary_constraints)
        final_score = distance + penalty

        # Map distance to a 0-100 confidence score
        confidence = round(1 / (1 + final_score) * 100, 1)

        scored.append(
            {
                "id": meal.get("id"),
                "name": meal.get("name"),
                "category": meal.get("category"),
                "calories_kcal": cal or None,
                "protein_g": pro or None,
                "carbohydrates_g": car or None,
                "fat_g": fat or None,
                "fiber_g": meal.get("fiber_g"),
                "meal_type_name": meal.get("meal_type_name"),
                "picture_url": meal.get("picture_url"),
                "confidence_score": confidence,
                "constraint_violations": violations,
                "_score": final_score,
            }
        )

    scored.sort(key=lambda x: x["_score"])

    result = []
    for item in scored[:top_n]:
        item.pop("_score", None)
        result.append(item)

    return result


def reload_model() -> None:
    """Force-reload the model from disk (useful after retraining)."""
    global _model
    _model = None
    _get_model()
