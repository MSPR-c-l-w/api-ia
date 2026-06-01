"""Métriques d'évaluation du moteur nutritionnel (MSE, RMSE, RSS, TSS, R²).

Deux axes de mesure :

1. **Lookup accuracy** — compare les macros estimées par le NutritionLookupService
   aux valeurs de référence du backend (dataset Kaggle validé).
   Mesure la précision du lookup sur : calories, protéines, glucides, lipides, fibres.

2. **Imbalance accuracy** — compare les macros réelles d'un repas aux cibles
   du HealthProfile. Un repas parfaitement équilibré aurait R² = 1.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import mean_squared_error, r2_score

from app.contexts.nutrition.domain.models import HealthProfile, Macros

# ---------------------------------------------------------------------------
# 1. Lookup accuracy
# ---------------------------------------------------------------------------


def compute_lookup_metrics(
    samples: list[tuple[Macros, Macros]],
) -> dict[str, dict[str, float]]:
    """Compare macros estimées (pred) vs macros réelles (true) par nutriment.

    Paramètres
    ----------
    samples :
        Liste de (macros_estimées, macros_réelles).
        ``macros_estimées`` provient du NutritionLookupService.
        ``macros_réelles`` provient du backend (valeurs Kaggle validées).

    Retourne
    --------
    dict par nutriment : calories, proteins_g, carbs_g, fats_g, fibers_g
    Chacun contient : mse, rmse, rss, tss, r2, n_samples
    """
    if not samples:
        raise ValueError("La liste de samples ne peut pas être vide.")

    nutrients = ["calories", "proteins_g", "carbs_g", "fats_g", "fibers_g"]
    results: dict[str, dict[str, float]] = {}

    for nutrient in nutrients:
        y_pred = np.array([getattr(pred, nutrient) for pred, _ in samples], dtype=float)
        y_true = np.array([getattr(true, nutrient) for _, true in samples], dtype=float)

        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        rss = float(np.sum((y_true - y_pred) ** 2))
        tss = float(np.sum((y_true - y_true.mean()) ** 2))
        r2 = float(r2_score(y_true, y_pred)) if len(samples) >= 2 else float("nan")

        results[nutrient] = {
            "mse": round(mse, 4),
            "rmse": round(rmse, 4),
            "rss": round(rss, 4),
            "tss": round(tss, 4),
            "r2": round(r2, 4),
            "n_samples": len(samples),
        }

    return results


# ---------------------------------------------------------------------------
# 2. Imbalance accuracy (meal vs targets)
# ---------------------------------------------------------------------------

_MEAL_FRACTION = 1 / 3


def compute_imbalance_metrics(
    meals: list[tuple[Macros, HealthProfile]],
) -> dict[str, dict[str, float]]:
    """Métriques d'écart repas vs cibles nutritionnelles.

    Paramètres
    ----------
    meals :
        Liste de (macros_repas, health_profile).
        y_true = cible du repas (daily_target / 3)
        y_pred = valeurs réelles du repas

    Retourne
    --------
    dict par nutriment avec mse, rmse, rss, tss, r2, mean_deviation_pct
    """
    if not meals:
        raise ValueError("La liste de meals ne peut pas être vide.")

    nutrient_targets = {
        "calories": lambda hp: hp.daily_calories_target * _MEAL_FRACTION,
        "proteins_g": lambda hp: hp.proteins_target_g * _MEAL_FRACTION,
        "carbs_g": lambda hp: hp.carbs_target_g * _MEAL_FRACTION,
        "fats_g": lambda hp: hp.fats_target_g * _MEAL_FRACTION,
        "fibers_g": lambda hp: hp.fibers_target_g * _MEAL_FRACTION,
    }

    results: dict[str, dict[str, float]] = {}

    for nutrient, target_fn in nutrient_targets.items():
        y_pred = np.array(
            [getattr(macros, nutrient) for macros, _ in meals], dtype=float
        )
        y_true = np.array([target_fn(hp) for _, hp in meals], dtype=float)

        mse = float(mean_squared_error(y_true, y_pred))
        rmse = float(np.sqrt(mse))
        rss = float(np.sum((y_true - y_pred) ** 2))
        tss = float(np.sum((y_true - y_true.mean()) ** 2))
        r2 = float(r2_score(y_true, y_pred)) if len(meals) >= 2 else float("nan")
        # Deviation moyenne en %
        with np.errstate(divide="ignore", invalid="ignore"):
            dev_pct = np.where(y_true > 0, (y_pred - y_true) / y_true * 100, 0.0)
        mean_dev_pct = float(np.mean(dev_pct))

        results[nutrient] = {
            "mse": round(mse, 4),
            "rmse": round(rmse, 4),
            "rss": round(rss, 4),
            "tss": round(tss, 4),
            "r2": round(r2, 4),
            "mean_deviation_pct": round(mean_dev_pct, 2),
            "n_samples": len(meals),
        }

    return results
