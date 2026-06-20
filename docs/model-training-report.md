# Rapport d'entraînement — Modèle de scoring sportif (`ExerciseScoringModel`)

Généré automatiquement par `scripts/train_workout_model.py` le 2026-06-20T18:08:47.122087+00:00.

## 1. Données

| Source | Échantillons |
|---|---|
| Réels (MongoDB `workout_feedbacks`) | 0 |
| Synthétiques (bootstrap, 300 profils simulés) | 1800 |
| **Total** | 1800 |
| Train (80%) | 1440 |
| Test (20%, hold-out) | 360 |

Label binaire : `satisfait = 1` si note réelle/simulée ≥ 4 (sur 5), `0` sinon.

## 2. Balayage du taux d'apprentissage (learning_rate)

Validation croisée stratifiée 5-fold sur le train set, métrique = F1 :

| learning_rate | F1 moyen (CV) | écart-type |
|---|---|---|
| 0.01 | 0.7952 | 0.034 |
| 0.05 | 0.8301 | 0.0191 |
| 0.1 | 0.8259 | 0.0197 |
| 0.2 | 0.8235 | 0.0179 |
| 0.3 | 0.8192 | 0.0171 |

**Meilleur learning_rate retenu : `0.05`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | 0.8389 |
| Précision | 0.7899 |
| Rappel (recall) | 0.7899 |
| F1-score | 0.7899 |
| R² (proba prédite vs note normalisée) | 0.5389 |
| RMSE | 0.3301 |

**Matrice de confusion :**

|  | Prédit négatif | Prédit positif |
|---|---|---|
| **Réel négatif** | 193 (TN) | 29 (FP) |
| **Réel positif** | 29 (FN) | 109 (TP) |

- Taux de faux positifs (FPR) : 0.1306
- Taux de faux négatifs (FNR) : 0.2101

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
| objective_match | 0.5911 |
| equipment_available | 0.1891 |
| level_diff | 0.1507 |
| limitation_conflict | 0.0517 |
| n_equipment_required | 0.0083 |
| n_contraindications | 0.0053 |
| preference_overlap_ratio | 0.0038 |

À comparer aux poids fixes de l'ancienne heuristique (0.40 objectif / 0.25 niveau /
0.20 matériel / 0.10 préférences / 0.05 limitations) — le modèle confirme l'objectif
comme facteur dominant mais réajuste les autres poids à partir des données.

## 5. Artefact

Modèle sérialisé : `C:\Users\dagas\api-ia\app\contexts\workout\domain\data\exercise_scoring_model.joblib`
