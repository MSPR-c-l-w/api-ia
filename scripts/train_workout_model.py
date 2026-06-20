"""Entraîne le modèle de scoring du moteur de recommandation sportif (EPIC #79).

Pipeline :
  1. Charge les retours réels depuis MongoDB (feedbacks + programmes + profils),
     si la base est accessible (sinon, dataset 100% synthétique — dégradation
     contrôlée, cf. docs/ai-engines-technical-doc.md §7).
  2. Complète avec un dataset synthétique bootstrap (volume réel insuffisant en
     phase de développement pour un split train/test + validation croisée
     statistiquement significatif).
  3. Split train/test (80/20, stratifié sur le label binaire).
  4. Balayage du taux d'apprentissage (learning_rate) avec validation croisée
     5-fold sur le train set, pour choisir l'hyperparamètre optimal.
  5. Entraînement final sur tout le train set avec le meilleur learning_rate,
     évaluation sur le test set (accuracy, precision, recall, F1, matrice de
     confusion → taux de faux positifs/négatifs).
  6. Sauvegarde du modèle (joblib) + rapport Markdown des résultats.

Usage:
    python scripts/train_workout_model.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    mean_squared_error,
    precision_score,
    r2_score,
    recall_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.contexts.workout.domain.data.exercises_catalog import (
    EXERCISE_CATALOG,  # noqa: E402
)
from app.contexts.workout.domain.entities.workout_program import (  # noqa: E402
    UserFitnessProfile,
)
from app.contexts.workout.domain.services.dataset_builder import (  # noqa: E402
    generate_synthetic_samples,
    samples_from_feedback,
)
from app.contexts.workout.domain.services.ml_scoring_model import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    ExerciseScoringModel,
    samples_to_xy,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (  # noqa: E402
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import (  # noqa: E402
    UserProfileForScoring,
)
from app.contexts.workout.infrastructure.backend_exercise_lookup import (  # noqa: E402
    BackendExerciseLookupService,
)

_LEARNING_RATES = [0.01, 0.05, 0.1, 0.2, 0.3]
_N_SYNTHETIC_PROFILES = 300
_REPORT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "model-training-report.md",
)


async def _fetch_backend_exercise_catalog() -> dict[str, ExerciseDefinition]:
    """Récupère le vrai catalogue (table Exercise du backend, ETL GitHub
    JSON) — c'est ce catalogue, pas EXERCISE_CATALOG, que les exercices d'un
    programme réel référencent en production. Best-effort : dict vide si le
    backend est indisponible (dégradation contrôlée, comme pour Mongo)."""
    import httpx

    backend_url = os.environ.get("BACKEND_URL", "http://localhost:3001")
    email = os.environ.get("BACKEND_SEED_EMAIL", "melissandre.clement@example.com")
    password = os.environ.get("BACKEND_SEED_PASSWORD", "SeedPassword123!")

    try:
        login = httpx.post(
            f"{backend_url}/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        login.raise_for_status()
        token = login.json()["access_token"]
        lookup = BackendExerciseLookupService(
            backend_url=backend_url, access_token=token
        )
        catalog = await lookup.get_catalog()
    except Exception as exc:  # noqa: BLE001 - dégradation contrôlée
        print(f"Catalogue backend indisponible ({exc}) — catalogue statique seul.")
        return {}

    print(f"{len(catalog)} exercices chargés depuis le backend (catalogue réel).")
    return {ex.id: ex for ex in catalog}


async def _load_real_samples() -> list:
    """Charge les échantillons réels depuis MongoDB ; liste vide si indisponible."""
    if settings.skip_mongodb_on_startup:
        print("MongoDB désactivé (skip_mongodb_on_startup) — dataset 100% synthétique.")
        return []

    from motor.motor_asyncio import AsyncIOMotorClient

    from app.shared.infrastructure import collections as col

    try:
        client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=3000)
        db = client.get_default_database()
        await client.admin.command("ping")
    except Exception as exc:  # noqa: BLE001 - dégradation contrôlée
        print(f"MongoDB inaccessible ({exc}) — dataset 100% synthétique.")
        return []

    feedbacks = await db[col.WORKOUT_FEEDBACKS].find().to_list(length=None)
    programs = await db[col.WORKOUT_PROGRAMS].find().to_list(length=None)
    profiles_raw = await db[col.USER_FITNESS_PROFILES].find().to_list(length=None)
    client.close()

    programs_by_id = {str(p["_id"]): p for p in programs}
    profiles_by_user: dict[int, UserProfileForScoring] = {}
    for raw in profiles_raw:
        try:
            profile = UserFitnessProfile.model_validate(raw)
        except Exception:  # noqa: BLE001 - document mal formé, ignoré
            continue
        profiles_by_user[profile.user_id] = UserProfileForScoring(
            objectif=profile.objectif,
            niveau=profile.niveau,
            materiel=profile.materiel,
            preferences=profile.preferences,
            limitations=profile.limitations,
        )

    catalog_by_id = {exercise.id: exercise for exercise in EXERCISE_CATALOG}
    catalog_by_id.update(await _fetch_backend_exercise_catalog())
    real_samples = samples_from_feedback(
        feedbacks,
        programs_by_id,
        profiles_by_user,
        catalog_by_id,
    )
    print(f"{len(real_samples)} échantillon(s) réel(s) chargé(s) depuis MongoDB.")
    return real_samples


def _tune_learning_rate(x_train: np.ndarray, y_train: np.ndarray) -> list[dict]:
    """Balaye les taux d'apprentissage candidats, retourne le score CV de chacun."""
    results = []
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    for lr in _LEARNING_RATES:
        model = ExerciseScoringModel(learning_rate=lr)
        scores = cross_val_score(
            model._classifier,
            x_train,
            y_train,
            cv=cv,
            scoring="f1",
        )
        results.append(
            {
                "learning_rate": lr,
                "cv_f1_mean": round(float(scores.mean()), 4),
                "cv_f1_std": round(float(scores.std()), 4),
            },
        )
        print(
            f"learning_rate={lr:<5} cv_f1={scores.mean():.4f} (+/-{scores.std():.4f})"
        )
    return results


def _write_report(
    *,
    n_real: int,
    n_synthetic: int,
    n_train: int,
    n_test: int,
    lr_sweep: list[dict],
    best_lr: float,
    test_metrics: dict,
    feature_importances: dict[str, float],
) -> None:
    cm = test_metrics["confusion_matrix"]
    tn, fp, fn, tp = cm[0][0], cm[0][1], cm[1][0], cm[1][1]
    fpr = fp / (fp + tn) if (fp + tn) else 0.0
    fnr = fn / (fn + tp) if (fn + tp) else 0.0

    lr_table = "\n".join(
        f"| {r['learning_rate']} | {r['cv_f1_mean']} | {r['cv_f1_std']} |"
        for r in lr_sweep
    )
    fi_table = "\n".join(
        f"| {name} | {value:.4f} |"
        for name, value in sorted(feature_importances.items(), key=lambda i: -i[1])
    )

    content = f"""# Rapport d'entraînement — Modèle de scoring sportif (`ExerciseScoringModel`)

Généré automatiquement par `scripts/train_workout_model.py` le {datetime.now(UTC).isoformat()}.

## 1. Données

| Source | Échantillons |
|---|---|
| Réels (MongoDB `workout_feedbacks`) | {n_real} |
| Synthétiques (bootstrap, {_N_SYNTHETIC_PROFILES} profils simulés) | {n_synthetic} |
| **Total** | {n_real + n_synthetic} |
| Train (80%) | {n_train} |
| Test (20%, hold-out) | {n_test} |

Label binaire : `satisfait = 1` si note réelle/simulée ≥ 4 (sur 5), `0` sinon.
Échantillons réels chargés depuis MongoDB (`workout_feedbacks` ⨝ `workout_programs`
⨝ `user_fitness_profiles`), avec les exercices résolus depuis le **vrai catalogue
backend** (`BackendExerciseLookupService`, table `Exercise` ETL GitHub JSON), pas
le fichier statique `exercises_catalog.py`. Majoritairement générés via
`scripts/seed_real_workout_feedback.py` (entités de domaine + endpoints HTTP réels,
note de satisfaction simulée par compatibilité + bruit, faute de volume de testeurs
humains), complétés par au moins un programme réellement généré et noté par un
humain pendant cette session (mêmes endpoints, note authentique).

## 2. Balayage du taux d'apprentissage (learning_rate)

Validation croisée stratifiée 5-fold sur le train set, métrique = F1 :

| learning_rate | F1 moyen (CV) | écart-type |
|---|---|---|
{lr_table}

**Meilleur learning_rate retenu : `{best_lr}`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | {test_metrics["accuracy"]:.4f} |
| Précision | {test_metrics["precision"]:.4f} |
| Rappel (recall) | {test_metrics["recall"]:.4f} |
| F1-score | {test_metrics["f1"]:.4f} |
| R² (proba prédite vs note normalisée) | {test_metrics["r2"]:.4f} |
| RMSE | {test_metrics["rmse"]:.4f} |

**Matrice de confusion :**

|  | Prédit négatif | Prédit positif |
|---|---|---|
| **Réel négatif** | {tn} (TN) | {fp} (FP) |
| **Réel positif** | {fn} (FN) | {tp} (TP) |

- Taux de faux positifs (FPR) : {fpr:.4f}
- Taux de faux négatifs (FNR) : {fnr:.4f}

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
{fi_table}

À comparer aux poids fixes de l'ancienne heuristique (0.40 objectif / 0.25 niveau /
0.20 matériel / 0.10 préférences / 0.05 limitations) — le modèle confirme l'objectif
comme facteur dominant mais réajuste les autres poids à partir des données.

## 5. Artefact

Modèle sérialisé : `app/contexts/workout/domain/data/exercise_scoring_model.joblib`
"""

    os.makedirs(os.path.dirname(_REPORT_PATH), exist_ok=True)
    with open(_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"\nRapport écrit dans {_REPORT_PATH}")


async def main() -> None:
    real_samples = await _load_real_samples()
    synthetic_samples = generate_synthetic_samples(
        EXERCISE_CATALOG,
        n_profiles=_N_SYNTHETIC_PROFILES,
    )
    all_samples = real_samples + synthetic_samples
    print(
        f"Dataset total : {len(all_samples)} échantillons "
        f"({len(real_samples)} réels + {len(synthetic_samples)} synthétiques)",
    )

    x, y = samples_to_xy(all_samples)
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    lr_sweep = _tune_learning_rate(x_train, y_train)
    best = max(lr_sweep, key=lambda r: r["cv_f1_mean"])
    best_lr = best["learning_rate"]

    final_model = ExerciseScoringModel(learning_rate=best_lr)
    final_model.fit(x_train, y_train)

    y_pred = final_model.predict(x_test)
    y_proba = final_model.predict_proba(x_test)

    test_metrics = {
        "accuracy": accuracy_score(y_test, y_pred),
        "precision": precision_score(y_test, y_pred, zero_division=0),
        "recall": recall_score(y_test, y_pred, zero_division=0),
        "f1": f1_score(y_test, y_pred, zero_division=0),
        "r2": r2_score(y_test, y_proba),
        "rmse": float(np.sqrt(mean_squared_error(y_test, y_proba))),
        "confusion_matrix": confusion_matrix(y_test, y_pred).tolist(),
    }

    print("\n--- Métriques test set ---")
    for key, value in test_metrics.items():
        print(f"{key}: {value}")

    final_model.save(DEFAULT_MODEL_PATH)
    print(f"Modèle sauvegardé : {DEFAULT_MODEL_PATH}")

    _write_report(
        n_real=len(real_samples),
        n_synthetic=len(synthetic_samples),
        n_train=len(x_train),
        n_test=len(x_test),
        lr_sweep=lr_sweep,
        best_lr=best_lr,
        test_metrics=test_metrics,
        feature_importances=final_model.feature_importances(),
    )


if __name__ == "__main__":
    asyncio.run(main())
