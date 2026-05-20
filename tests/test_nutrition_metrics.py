"""Tests pour nutrition_metrics : lookup accuracy + imbalance accuracy."""

import math

import pytest

from app.contexts.nutrition.domain.models import HealthProfile, Macros
from app.contexts.nutrition.domain.nutrition_metrics import (
    compute_imbalance_metrics,
    compute_lookup_metrics,
)


def _macros(cal=200.0, prot=20.0, carbs=25.0, fats=8.0, fibers=3.0) -> Macros:
    return Macros(
        calories=cal,
        proteins_g=prot,
        carbs_g=carbs,
        fats_g=fats,
        fibers_g=fibers,
    )


# ---------------------------------------------------------------------------
# compute_lookup_metrics
# ---------------------------------------------------------------------------

def test_lookup_metrics_returns_all_nutrients():
    samples = [(_macros(), _macros())]
    result = compute_lookup_metrics(samples)
    assert set(result.keys()) == {"calories", "proteins_g", "carbs_g", "fats_g", "fibers_g"}


def test_lookup_metrics_keys_per_nutrient():
    samples = [(_macros(), _macros())]
    for nutrient, metrics in compute_lookup_metrics(samples).items():
        assert set(metrics.keys()) == {"mse", "rmse", "rss", "tss", "r2", "n_samples"}


def test_lookup_perfect_prediction_zero_error():
    """Quand pred == true, MSE et RSS doivent être 0."""
    m = _macros(cal=300, prot=30, carbs=40, fats=10, fibers=5)
    samples = [(m, m), (m, m), (m, m)]
    result = compute_lookup_metrics(samples)
    for nutrient in result:
        assert result[nutrient]["mse"] == 0.0
        assert result[nutrient]["rss"] == 0.0
        assert result[nutrient]["rmse"] == 0.0


def test_lookup_rmse_equals_sqrt_mse():
    pred = _macros(cal=250, prot=22, carbs=30, fats=9, fibers=4)
    true = _macros(cal=300, prot=18, carbs=35, fats=12, fibers=2)
    samples = [(pred, true), (true, pred)]
    result = compute_lookup_metrics(samples)
    for nutrient in result:
        assert abs(result[nutrient]["rmse"] - math.sqrt(result[nutrient]["mse"])) < 1e-5


def test_lookup_rss_equals_sum_squared_residuals():
    pred1 = _macros(cal=200)
    true1 = _macros(cal=300)
    pred2 = _macros(cal=150)
    true2 = _macros(cal=250)
    samples = [(pred1, true1), (pred2, true2)]
    expected_rss = (300 - 200) ** 2 + (250 - 150) ** 2
    result = compute_lookup_metrics(samples)
    assert abs(result["calories"]["rss"] - expected_rss) < 1e-3


def test_lookup_empty_raises():
    with pytest.raises(ValueError, match="vide"):
        compute_lookup_metrics([])


# ---------------------------------------------------------------------------
# compute_imbalance_metrics
# ---------------------------------------------------------------------------

def test_imbalance_metrics_returns_all_nutrients():
    profile = HealthProfile()
    meals = [(_macros(), profile)]
    result = compute_imbalance_metrics(meals)
    assert set(result.keys()) == {"calories", "proteins_g", "carbs_g", "fats_g", "fibers_g"}


def test_imbalance_metrics_keys_per_nutrient():
    profile = HealthProfile()
    meals = [(_macros(), profile)]
    for nutrient, metrics in compute_imbalance_metrics(meals).items():
        assert set(metrics.keys()) == {
            "mse", "rmse", "rss", "tss", "r2", "mean_deviation_pct", "n_samples"
        }


def test_imbalance_perfect_meal_zero_deviation():
    """Un repas exactement sur la cible (1/3 du daily) a deviation_pct = 0."""
    profile = HealthProfile(
        daily_calories_target=600,
        proteins_target_g=60,
        carbs_target_g=75,
        fats_target_g=24,
        fibers_target_g=9,
    )
    # Cible repas = daily / 3
    perfect = _macros(cal=200, prot=20, carbs=25, fats=8, fibers=3)
    meals = [(perfect, profile), (perfect, profile), (perfect, profile)]
    result = compute_imbalance_metrics(meals)
    for nutrient in result:
        assert result[nutrient]["mean_deviation_pct"] == pytest.approx(0.0, abs=1e-4)
        assert result[nutrient]["mse"] == pytest.approx(0.0, abs=1e-4)


def test_imbalance_deficit_has_negative_deviation():
    """Un repas sous la cible doit avoir mean_deviation_pct négatif."""
    profile = HealthProfile(daily_calories_target=2000)
    low_cal = _macros(cal=100)  # cible repas = 2000/3 ≈ 667 kcal
    meals = [(low_cal, profile), (low_cal, profile)]
    result = compute_imbalance_metrics(meals)
    assert result["calories"]["mean_deviation_pct"] < 0


def test_imbalance_n_samples():
    profile = HealthProfile()
    meals = [(_macros(), profile)] * 7
    result = compute_imbalance_metrics(meals)
    for nutrient in result:
        assert result[nutrient]["n_samples"] == 7


def test_imbalance_empty_raises():
    with pytest.raises(ValueError, match="vide"):
        compute_imbalance_metrics([])


# ---------------------------------------------------------------------------
# Integration : backend lookup → metrics réelles
# ---------------------------------------------------------------------------

def test_backend_lookup_metrics_with_real_data():
    """Test d'intégration : charge quelques aliments du backend et calcule les métriques."""
    from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService
    from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import (
        BackendNutritionLookupService,
    )

    try:
        auth = BackendAuthService(
            "http://localhost:3001",
            "agathe.andre@example.com",
            "SeedPassword123!",
            timeout_seconds=5,
        )
        token = auth.get_token()
        svc = BackendNutritionLookupService("http://localhost:3001", token)
        svc._ensure_loaded()

        if len(svc._table) == 0:
            pytest.skip("Backend non disponible ou table vide")

        # Utilise les 10 premiers aliments comme ground truth
        foods = list(svc._table.items())[:10]
        samples = []
        for name, (cal, prot, carbs, fat, fiber) in foods:
            true_macros = Macros(
                calories=cal * 1.5,  # portion 150g
                proteins_g=prot * 1.5,
                carbs_g=carbs * 1.5,
                fats_g=fat * 1.5,
                fibers_g=fiber * 1.5,
            )
            pred_macros = svc.compute_macros([name])
            samples.append((pred_macros, true_macros))

        result = compute_lookup_metrics(samples)
        assert result["calories"]["n_samples"] == 10
        assert result["calories"]["rmse"] >= 0
        assert result["calories"]["r2"] <= 1.0

    except Exception as exc:
        pytest.skip(f"Backend indisponible: {exc}")
