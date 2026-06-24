"""Extraction de features pour la classification du type de repas (EPIC #79).

Convertit les macronutriments bruts d'un aliment (tels que renvoyés par le
backend NestJS — table ``Nutrition``) en un vecteur numérique exploitable par
``MealTypeModel``. Les noms de champs correspondent exactement au contrat
``GET /nutrition`` (voir documentation/api-reference.md du backend).
"""

from __future__ import annotations

import json
from pathlib import Path

# Catégories réelles de la table Nutrition, récupérées via un vrai appel
# GET /nutrition (scripts/train_meal_type_model.py), pas une liste copiée à
# la main. Persistées ici en JSON (artefact généré, comme le .joblib du
# modèle) pour que l'API de production charge exactement les mêmes colonnes
# que celles utilisées à l'entraînement — un modèle scikit-learn entraîné
# attend un vecteur de taille fixe, donc cette liste doit rester stable
# entre deux entraînements, pas recalculée dynamiquement à chaque requête.
DEFAULT_CATEGORIES_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "meal_type_categories.json"
)


def load_known_categories(path: Path | str = DEFAULT_CATEGORIES_PATH) -> list[str]:
    """Charge la liste des catégories connues depuis le fichier généré par
    l'entraînement. Liste vide si absent (avant le premier entraînement) —
    toutes les catégories tombent alors dans le bucket "autre" (signal
    additif, jamais bloquant)."""
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []


_KNOWN_CATEGORIES: list[str] = load_known_categories()

FEATURE_NAMES: list[str] = []


def _rebuild_feature_names() -> None:
    FEATURE_NAMES[:] = [
        "calories",
        "protein_g",
        "carbs_g",
        "fat_g",
        "fiber_g",
        "sugar_g",
        "sodium_mg",
        "cholesterol_mg",
        *(f"category_{c}" for c in _KNOWN_CATEGORIES),
        "category_autre",
    ]


_rebuild_feature_names()


def set_known_categories(
    categories: list[str],
    path: Path | str = DEFAULT_CATEGORIES_PATH,
) -> None:
    """Met à jour la liste des catégories connues (en mémoire + sur disque)
    à partir de données fraîchement récupérées via un vrai appel API — à
    appeler depuis scripts/train_meal_type_model.py juste après avoir
    récupéré le catalogue, avant de construire le dataset d'entraînement."""
    sorted_categories = sorted({c for c in categories if c})
    _KNOWN_CATEGORIES[:] = sorted_categories
    _rebuild_feature_names()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted_categories, f, ensure_ascii=False, indent=2)


def extract_features(item: dict) -> list[float]:
    """Vecteur de features numériques à partir d'un item ``Nutrition`` brut.

    8 macronutriments + encodage one-hot de la catégorie (une colonne par
    catégorie connue + "autre"). La catégorie est optionnelle — un item sans
    champ ``category`` (ex. appelé depuis meal_composer, qui ne la propage
    pas dans le catalogue) retombe sur le bucket "autre".
    """
    category = item.get("category")
    category_onehot = [1.0 if category == c else 0.0 for c in _KNOWN_CATEGORIES]
    category_onehot.append(1.0 if category not in _KNOWN_CATEGORIES else 0.0)
    return [
        float(item.get("calories_kcal") or 0.0),
        float(item.get("protein_g") or 0.0),
        float(item.get("carbohydrates_g") or 0.0),
        float(item.get("fat_g") or 0.0),
        float(item.get("fiber_g") or 0.0),
        float(item.get("sugar_g") or 0.0),
        float(item.get("sodium_mg") or 0.0),
        float(item.get("cholesterol_mg") or 0.0),
        *category_onehot,
    ]
