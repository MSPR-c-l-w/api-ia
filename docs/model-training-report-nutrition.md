# Rapport d'entraînement — Classification du type de repas (`MealTypeModel`)

Généré automatiquement par `scripts/train_meal_type_model.py` le 2026-06-20T19:30:48.320878+00:00.

## 1. Données

Source : catalogue réel `Nutrition` du backend (dataset Kaggle importé via ETL,
validé par revue humaine — voir documentation/architecture.md §Architecture ETL).
Label : `meal_type_name`, colonne réelle du dataset (pas une règle interne).

| Classe | Échantillons |
|---|---|
| Petit-déjeuner | 82 |
| Collation | 166 |
| Dîner | 211 |
| Déjeuner | 136 |

| | |
|---|---|
| Total (après filtrage des lignes corrompues) | 595 |
| Train (80%) | 476 |
| Test (20%, hold-out) | 119 |

## 2. Balayage du taux d'apprentissage (learning_rate)

Validation croisée stratifiée 5-fold sur le train set, métrique = F1 macro :

| learning_rate | F1 macro moyen (CV) | écart-type |
|---|---|---|
| 0.01 | 0.3317 | 0.0175 |
| 0.05 | 0.3961 | 0.0175 |
| 0.1 | 0.3982 | 0.022 |
| 0.2 | 0.3912 | 0.0156 |
| 0.3 | 0.3946 | 0.0384 |

**Meilleur learning_rate retenu : `0.1`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | 0.4622 |
| Précision (macro) | 0.4127 |
| Rappel (recall, macro) | 0.4120 |
| F1-score (macro) | 0.4056 |
| Baseline classe majoritaire (`Dîner`) | 0.3550 |

Le modèle bat la baseline naïve (toujours prédire la classe majoritaire) de
**+10.7 points** —
sur un problème à 4 classes avec un signal faible (les macros seules ne
déterminent pas pleinement le créneau de repas : un yaourt peut être pris au
petit-déjeuner ou en collation), c'est un résultat honnête, pas gonflé
artificiellement.

**Matrice de confusion :**

| Réel \ Prédit | Petit-déjeuner | Déjeuner | Dîner | Collation |
|---|---|---|---|---|
| **Petit-déjeuner** | 2 | 2 | 3 | 10 |
| **Déjeuner** | 2 | 10 | 12 | 3 |
| **Dîner** | 4 | 13 | 22 | 3 |
| **Collation** | 0 | 5 | 7 | 21 |

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
| sugar_g | 0.2029 |
| sodium_mg | 0.1807 |
| calories | 0.1448 |
| carbs_g | 0.1184 |
| protein_g | 0.1086 |
| fat_g | 0.0940 |
| cholesterol_mg | 0.0777 |
| fiber_g | 0.0729 |

## 5. Artefact

Modèle sérialisé : `app/contexts/nutrition/domain/data/meal_type_model.joblib`
