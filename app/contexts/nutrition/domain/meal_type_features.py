"""Extraction de features pour la classification du type de repas (EPIC #79).

Convertit les macronutriments bruts d'un aliment (tels que renvoyés par le
backend NestJS — table ``Nutrition``) en un vecteur numérique exploitable par
``MealTypeModel``. Les noms de champs correspondent exactement au contrat
``GET /nutrition`` (voir documentation/api-reference.md du backend).
"""

from __future__ import annotations

FEATURE_NAMES: list[str] = [
    "calories",
    "protein_g",
    "carbs_g",
    "fat_g",
    "fiber_g",
    "sugar_g",
    "sodium_mg",
    "cholesterol_mg",
]


def extract_features(item: dict) -> list[float]:
    """Vecteur de 8 features numériques à partir d'un item ``Nutrition`` brut."""
    return [
        float(item.get("calories_kcal") or 0.0),
        float(item.get("protein_g") or 0.0),
        float(item.get("carbohydrates_g") or 0.0),
        float(item.get("fat_g") or 0.0),
        float(item.get("fiber_g") or 0.0),
        float(item.get("sugar_g") or 0.0),
        float(item.get("sodium_mg") or 0.0),
        float(item.get("cholesterol_mg") or 0.0),
    ]
