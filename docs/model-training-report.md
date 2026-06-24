# Rapport d'entraînement — Modèle de scoring sportif (`ExerciseScoringModel`)

Généré automatiquement par `scripts/train_workout_model.py` le 2026-06-20T20:58:19.648051+00:00.

## 1. Données

| Source | Échantillons |
|---|---|
| Réels (MongoDB `workout_feedbacks`) | 7077 |
| Synthétiques (bootstrap, 300 profils simulés) | 1800 |
| **Total** | 8877 |
| Train (80%) | 7101 |
| Test (20%, hold-out) | 1776 |

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
| 0.01 | 0.7949 | 0.007 |
| 0.05 | 0.7962 | 0.0071 |
| 0.1 | 0.7925 | 0.0135 |
| 0.2 | 0.7873 | 0.014 |
| 0.3 | 0.7919 | 0.0158 |

**Meilleur learning_rate retenu : `0.05`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | 0.7264 |
| Précision | 0.7290 |
| Rappel (recall) | 0.8760 |
| F1-score | 0.7958 |
| R² (proba prédite vs note normalisée) | 0.2534 |
| RMSE | 0.4217 |

**Matrice de confusion :**

|  | Prédit négatif | Prédit positif |
|---|---|---|
| **Réel négatif** | 343 (TN) | 352 (FP) |
| **Réel positif** | 134 (FN) | 947 (TP) |

- Taux de faux positifs (FPR) : 0.5065
- Taux de faux négatifs (FNR) : 0.1240

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
| objective_match | 0.6199 |
| equipment_available | 0.1749 |
| level_diff | 0.1094 |
| n_contraindications | 0.0610 |
| limitation_conflict | 0.0154 |
| n_equipment_required | 0.0105 |
| preference_overlap_ratio | 0.0090 |

À comparer aux poids fixes de l'ancienne heuristique (0.40 objectif / 0.25 niveau /
0.20 matériel / 0.10 préférences / 0.05 limitations) — le modèle confirme l'objectif
comme facteur dominant mais réajuste les autres poids à partir des données.

## 5. Artefact

Modèle sérialisé : `app/contexts/workout/domain/data/exercise_scoring_model.joblib`
