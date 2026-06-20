# Rapport d'entraînement — Modèle de scoring sportif (`ExerciseScoringModel`)

Généré automatiquement par `scripts/train_workout_model.py` le 2026-06-20T20:16:04.245109+00:00.

## 1. Données

| Source | Échantillons |
|---|---|
| Réels (MongoDB `workout_feedbacks`) | 1650 |
| Synthétiques (bootstrap, 300 profils simulés) | 1800 |
| **Total** | 3450 |
| Train (80%) | 2760 |
| Test (20%, hold-out) | 690 |

Label binaire : `satisfait = 1` si note réelle/simulée ≥ 4 (sur 5), `0` sinon.
Échantillons réels chargés depuis MongoDB (`workout_feedbacks` ⨝ `workout_programs`
⨝ `user_fitness_profiles`), avec les exercices résolus depuis le **vrai catalogue
backend** (`BackendExerciseLookupService`, table `Exercise` ETL GitHub JSON), pas
le fichier statique `exercises_catalog.py`. Générés via `scripts/seed_real_workout_feedback.py`
(entités de domaine + endpoints HTTP réels — seule la note de satisfaction est
simulée, faute de testeurs humains à ce stade).

## 2. Balayage du taux d'apprentissage (learning_rate)

Validation croisée stratifiée 5-fold sur le train set, métrique = F1 :

| learning_rate | F1 moyen (CV) | écart-type |
|---|---|---|
| 0.01 | 0.4856 | 0.04 |
| 0.05 | 0.5049 | 0.0419 |
| 0.1 | 0.5148 | 0.0506 |
| 0.2 | 0.5168 | 0.0348 |
| 0.3 | 0.5173 | 0.0344 |

**Meilleur learning_rate retenu : `0.3`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | 0.7710 |
| Précision | 0.7760 |
| Rappel (recall) | 0.4273 |
| F1-score | 0.5511 |
| R² (proba prédite vs note normalisée) | 0.2845 |
| RMSE | 0.3974 |

**Matrice de confusion :**

|  | Prédit négatif | Prédit positif |
|---|---|---|
| **Réel négatif** | 435 (TN) | 28 (FP) |
| **Réel positif** | 130 (FN) | 97 (TP) |

- Taux de faux positifs (FPR) : 0.0605
- Taux de faux négatifs (FNR) : 0.5727

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
| n_contraindications | 0.2772 |
| objective_match | 0.2707 |
| equipment_available | 0.2137 |
| level_diff | 0.1167 |
| preference_overlap_ratio | 0.0459 |
| limitation_conflict | 0.0404 |
| n_equipment_required | 0.0354 |

À comparer aux poids fixes de l'ancienne heuristique (0.40 objectif / 0.25 niveau /
0.20 matériel / 0.10 préférences / 0.05 limitations) — le modèle confirme l'objectif
comme facteur dominant mais réajuste les autres poids à partir des données.

## 5. Artefact

Modèle sérialisé : `app/contexts/workout/domain/data/exercise_scoring_model.joblib`
