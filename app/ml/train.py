"""
Training script for the biometric-to-nutritional-targets model.

The model learns: user biometrics → optimal meal nutritional targets.
Ground truth is generated via the Mifflin-St Jeor BMR formula + activity factors,
which are the gold standard in sports nutrition.

Run directly to train and save the model:
    python -m app.ml.train
"""

import os
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "biometric_model.pkl")

ACTIVITY_LEVELS = [
    "sedentary",
    "lightly_active",
    "moderately_active",
    "very_active",
    "extra_active",
]

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}

MEAL_TYPES = ["breakfast", "lunch", "dinner", "snack"]

# Share of daily calories allocated to each meal type
MEAL_CALORIE_RATIOS = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.30,
    "snack": 0.10,
}

# [protein_pct, carbs_pct, fat_pct] per activity level (of meal calories)
MACRO_RATIOS = {
    "sedentary": (0.30, 0.40, 0.30),
    "lightly_active": (0.25, 0.50, 0.25),
    "moderately_active": (0.25, 0.55, 0.20),
    "very_active": (0.25, 0.55, 0.20),
    "extra_active": (0.20, 0.60, 0.20),
}


def _mifflin_st_jeor_bmr(weight_kg: float, height_cm: float, age: int, gender: str) -> float:
    """Mifflin-St Jeor BMR formula."""
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return base + 5 if gender == "male" else base - 161


def generate_training_data(n_samples: int = 6000, seed: int = 42) -> pd.DataFrame:
    """
    Generate synthetic training samples.
    Each sample represents a user profile + meal type → nutritional targets.
    """
    rng = np.random.RandomState(seed)
    rows = []

    for _ in range(n_samples):
        age = int(rng.randint(18, 80))
        weight = float(rng.uniform(45, 150))
        height = float(rng.uniform(150, 210))
        gender = rng.choice(["male", "female"])
        activity = rng.choice(ACTIVITY_LEVELS)
        meal_type = rng.choice(MEAL_TYPES)

        bmi = weight / (height / 100) ** 2

        bmr = _mifflin_st_jeor_bmr(weight, height, age, gender)
        tdee = bmr * ACTIVITY_FACTORS[activity]
        meal_calories = tdee * MEAL_CALORIE_RATIOS[meal_type]

        protein_pct, carbs_pct, fat_pct = MACRO_RATIOS[activity]
        protein_g = (meal_calories * protein_pct) / 4   # 4 kcal/g
        carbs_g = (meal_calories * carbs_pct) / 4       # 4 kcal/g
        fat_g = (meal_calories * fat_pct) / 9           # 9 kcal/g

        # Slight biological variability noise
        noise = rng.normal(1.0, 0.04)

        rows.append(
            {
                "age": age,
                "weight_kg": weight,
                "height_cm": height,
                "bmi": bmi,
                "gender_num": 1 if gender == "male" else 0,
                "activity_num": ACTIVITY_LEVELS.index(activity),
                "meal_type_num": MEAL_TYPES.index(meal_type),
                "target_calories": meal_calories * noise,
                "target_protein_g": protein_g * noise,
                "target_carbs_g": carbs_g * noise,
                "target_fat_g": fat_g * noise,
            }
        )

    return pd.DataFrame(rows)


def train_and_save_model(model_path: str = MODEL_PATH) -> Pipeline:
    """Train the biometric → nutritional targets model and persist it."""
    os.makedirs(os.path.dirname(model_path), exist_ok=True)

    df = generate_training_data()

    feature_cols = ["age", "weight_kg", "height_cm", "bmi", "gender_num", "activity_num", "meal_type_num"]
    target_cols = ["target_calories", "target_protein_g", "target_carbs_g", "target_fat_g"]

    X = df[feature_cols].values
    y = df[target_cols].values

    pipeline = Pipeline(
        [
            ("scaler", StandardScaler()),
            (
                "model",
                MultiOutputRegressor(
                    RandomForestRegressor(n_estimators=150, random_state=42, n_jobs=-1)
                ),
            ),
        ]
    )

    pipeline.fit(X, y)
    joblib.dump(pipeline, model_path)
    return pipeline


if __name__ == "__main__":
    print("Training biometric recommendation model...")
    train_and_save_model()
    print(f"Model saved to {MODEL_PATH}")
