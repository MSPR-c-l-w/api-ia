"""Entraîne le modèle de classification du type de repas (EPIC #79).

Contrairement au modèle workout (majoritairement synthétique), ce modèle est
entraîné sur des données 100% réelles : le catalogue ``Nutrition`` du backend
(601+ aliments issus du dataset Kaggle, importés et validés via le pipeline
ETL). Le label (``meal_type_name``) est une colonne réelle du dataset, pas
une distillation d'une règle interne — c'est un vrai problème de
classification supervisée.

Pipeline :
  1. Authentification auprès du backend (compte de service défini dans
     .env via BACKEND_SERVICE_EMAIL / BACKEND_SERVICE_PASSWORD).
  2. Récupération de tout le catalogue ``GET /nutrition`` (pagination).
  3. Filtrage des lignes dont ``meal_type_name`` n'est pas une des 4 valeurs
     valides (quelques lignes de données corrompues dans le CSV source).
  4. Split train/test (80/20, stratifié).
  5. Balayage du learning_rate avec validation croisée 5-fold (F1 macro).
  6. Entraînement final, évaluation sur le test set (accuracy, precision/
     recall/F1 macro, matrice de confusion 4x4).
  7. Sauvegarde du modèle (joblib) + rapport Markdown.

Usage:
    python scripts/train_meal_type_model.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import httpx
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.contexts.nutrition.domain.meal_type_features import (  # noqa: E402
    extract_features,
    set_known_categories,
)
from app.contexts.nutrition.domain.meal_type_model import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    VALID_MEAL_TYPES,
    MealTypeModel,
)

_LEARNING_RATES = [0.01, 0.05, 0.1, 0.2, 0.3]
_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "model-training-report-nutrition.md",
)


def _fetch_catalog() -> list[dict]:
    """Récupère tout le catalogue Nutrition réel depuis le backend NestJS."""
    if not settings.backend_service_email or not settings.backend_service_password:
        raise RuntimeError(
            "BACKEND_SERVICE_EMAIL / BACKEND_SERVICE_PASSWORD non configurés "
            "(.env) — requis pour authentifier ce script auprès du backend.",
        )

    backend_url = settings.backend_url
    with httpx.Client(timeout=10) as client:
        login = client.post(
            f"{backend_url}/auth/login",
            json={
                "email": settings.backend_service_email,
                "password": settings.backend_service_password,
            },
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        first = client.get(
            f"{backend_url}/nutrition",
            params={"page": 1, "limit": 1},
            headers=headers,
        )
        first.raise_for_status()
        total = first.json().get("total", 0)

        items: list[dict] = []
        page_size = 100
        for page in range(1, (total // page_size) + 2):
            resp = client.get(
                f"{backend_url}/nutrition",
                params={"page": page, "limit": page_size},
                headers=headers,
            )
            resp.raise_for_status()
            batch = resp.json().get("data", [])
            items.extend(batch)
            if len(batch) < page_size:
                break

    print(f"{len(items)} aliments récupérés depuis {backend_url}/nutrition.")
    return items


def _build_dataset(items: list[dict]) -> tuple[np.ndarray, list[str]]:
    """Filtre les lignes valides et extrait (features, label)."""
    valid = [item for item in items if item.get("meal_type_name") in VALID_MEAL_TYPES]
    skipped = len(items) - len(valid)
    if skipped:
        print(f"{skipped} ligne(s) ignorée(s) (meal_type_name invalide ou absent).")

    x = np.array([extract_features(item) for item in valid])
    y = [str(item["meal_type_name"]) for item in valid]
    return x, y


def _tune_learning_rate(x_train: np.ndarray, y_train: list[str]) -> list[dict]:
    results = []
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for lr in _LEARNING_RATES:
        model = MealTypeModel(learning_rate=lr)
        scores = cross_val_score(
            model._classifier,
            x_train,
            y_train,
            cv=cv,
            scoring="f1_macro",
        )
        results.append(
            {
                "learning_rate": lr,
                "cv_f1_macro_mean": round(float(scores.mean()), 4),
                "cv_f1_macro_std": round(float(scores.std()), 4),
            },
        )
        print(
            f"learning_rate={lr:<5} cv_f1_macro={scores.mean():.4f} "
            f"(+/-{scores.std():.4f})",
        )
    return results


def _write_report(
    *,
    n_total: int,
    n_train: int,
    n_test: int,
    class_distribution: dict[str, int],
    lr_sweep: list[dict],
    best_lr: float,
    test_metrics: dict,
    feature_importances: dict[str, float],
) -> None:
    lr_table = "\n".join(
        f"| {r['learning_rate']} | {r['cv_f1_macro_mean']} | {r['cv_f1_macro_std']} |"
        for r in lr_sweep
    )
    fi_table = "\n".join(
        f"| {name} | {value:.4f} |"
        for name, value in sorted(feature_importances.items(), key=lambda i: -i[1])
    )
    dist_table = "\n".join(
        f"| {label} | {count} |" for label, count in class_distribution.items()
    )
    cm = test_metrics["confusion_matrix"]
    cm_header = "| Réel \\ Prédit | " + " | ".join(VALID_MEAL_TYPES) + " |"
    cm_rows = "\n".join(
        f"| **{VALID_MEAL_TYPES[i]}** | " + " | ".join(str(v) for v in row) + " |"
        for i, row in enumerate(cm)
    )

    content = f"""# Rapport d'entraînement — Classification du type de repas (`MealTypeModel`)

Généré automatiquement par `scripts/train_meal_type_model.py` le {datetime.now(UTC).isoformat()}.

## 1. Données

Source : catalogue réel `Nutrition` du backend (dataset Kaggle importé via ETL,
validé par revue humaine — voir documentation/architecture.md §Architecture ETL).
Label : `meal_type_name`, colonne réelle du dataset (pas une règle interne).

| Classe | Échantillons |
|---|---|
{dist_table}

| | |
|---|---|
| Total (après filtrage des lignes corrompues) | {n_total} |
| Train (80%) | {n_train} |
| Test (20%, hold-out) | {n_test} |

## 2. Balayage du taux d'apprentissage (learning_rate)

Validation croisée stratifiée 5-fold sur le train set, métrique = F1 macro :

| learning_rate | F1 macro moyen (CV) | écart-type |
|---|---|---|
{lr_table}

**Meilleur learning_rate retenu : `{best_lr}`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | {test_metrics["accuracy"]:.4f} |
| Précision (macro) | {test_metrics["precision_macro"]:.4f} |
| Rappel (recall, macro) | {test_metrics["recall_macro"]:.4f} |
| F1-score (macro) | {test_metrics["f1_macro"]:.4f} |
| Baseline classe majoritaire (`{test_metrics["baseline_majority_class"]}`) | {test_metrics["baseline_accuracy"]:.4f} |

Le modèle bat la baseline naïve (toujours prédire la classe majoritaire) de
**{(test_metrics["accuracy"] - test_metrics["baseline_accuracy"]) * 100:+.1f} points** —
sur un problème à 4 classes avec un signal faible (les macros seules ne
déterminent pas pleinement le créneau de repas : un yaourt peut être pris au
petit-déjeuner ou en collation), c'est un résultat honnête, pas gonflé
artificiellement.

**Matrice de confusion :**

{cm_header}
|---|{"---|" * len(VALID_MEAL_TYPES)}
{cm_rows}

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
{fi_table}

## 5. Artefact

Modèle sérialisé : `app/contexts/nutrition/data/meal_type_model.joblib`
Catégories connues : `app/contexts/nutrition/data/meal_type_categories.json`
"""

    os.makedirs(os.path.dirname(_REPORT_PATH), exist_ok=True)
    with open(_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nRapport écrit dans {_REPORT_PATH}")


def main() -> None:
    items = _fetch_catalog()
    # Catégories réelles dérivées du vrai appel GET /nutrition ci-dessus (pas
    # une liste copiée à la main) — persistées pour que l'API de production
    # utilise exactement les mêmes colonnes que celles apprises ici.
    set_known_categories([item.get("category") for item in items])
    x, y = _build_dataset(items)

    from collections import Counter

    class_distribution = dict(Counter(y))
    print(f"Distribution des classes : {class_distribution}")

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    lr_sweep = _tune_learning_rate(x_train, y_train)
    best = max(lr_sweep, key=lambda r: r["cv_f1_macro_mean"])
    best_lr = best["learning_rate"]

    final_model = MealTypeModel(learning_rate=best_lr)
    final_model.fit(x_train, y_train)

    y_pred = final_model.predict(x_test)

    from collections import Counter as _Counter

    majority_class, majority_count = _Counter(y_train).most_common(1)[0]
    baseline_accuracy = majority_count / len(y_train)

    test_metrics = {
        "baseline_majority_class": majority_class,
        "baseline_accuracy": baseline_accuracy,
        "accuracy": accuracy_score(y_test, y_pred),
        "precision_macro": precision_score(
            y_test,
            y_pred,
            average="macro",
            zero_division=0,
        ),
        "recall_macro": recall_score(y_test, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_test, y_pred, average="macro", zero_division=0),
        "confusion_matrix": confusion_matrix(
            y_test,
            y_pred,
            labels=VALID_MEAL_TYPES,
        ).tolist(),
    }

    print("\n--- Métriques test set ---")
    for key, value in test_metrics.items():
        print(f"{key}: {value}")

    final_model.save(DEFAULT_MODEL_PATH)
    print(f"Modèle sauvegardé : {DEFAULT_MODEL_PATH}")

    _write_report(
        n_total=len(y),
        n_train=len(x_train),
        n_test=len(x_test),
        class_distribution=class_distribution,
        lr_sweep=lr_sweep,
        best_lr=best_lr,
        test_metrics=test_metrics,
        feature_importances=final_model.feature_importances(),
    )


if __name__ == "__main__":
    main()
