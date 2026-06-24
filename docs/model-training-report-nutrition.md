# Rapport d'entraînement — Classification du type de repas (`MealTypeModel`)

Généré automatiquement par `scripts/train_meal_type_model.py` le 2026-06-20T22:21:31.478435+00:00.

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
| 0.01 | 0.3807 | 0.0319 |
| 0.05 | 0.465 | 0.0331 |
| 0.1 | 0.4724 | 0.0267 |
| 0.2 | 0.4618 | 0.0504 |
| 0.3 | 0.4477 | 0.0395 |

**Meilleur learning_rate retenu : `0.1`** (entraînement final sur 100% du train set).

## 3. Performance sur le test set (hold-out, jamais vu à l'entraînement)

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | 0.5714 |
| Précision (macro) | 0.5222 |
| Rappel (recall, macro) | 0.5113 |
| F1-score (macro) | 0.5068 |
| Baseline classe majoritaire (`Dîner`) | 0.3550 |

Le modèle bat la baseline naïve (toujours prédire la classe majoritaire) de
**+21.6 points** —
sur un problème à 4 classes avec un signal faible (les macros seules ne
déterminent pas pleinement le créneau de repas : un yaourt peut être pris au
petit-déjeuner ou en collation), c'est un résultat honnête, pas gonflé
artificiellement.

**Matrice de confusion :**

| Réel \ Prédit | Petit-déjeuner | Déjeuner | Dîner | Collation |
|---|---|---|---|---|
| **Petit-déjeuner** | 3 | 1 | 2 | 11 |
| **Déjeuner** | 2 | 13 | 12 | 0 |
| **Dîner** | 2 | 7 | 29 | 4 |
| **Collation** | 1 | 7 | 2 | 23 |

## 4. Importance des features (poids appris par le modèle)

| Feature | Importance |
|---|---|
| sugar_g | 0.1915 |
| sodium_mg | 0.1398 |
| calories | 0.0791 |
| protein_g | 0.0751 |
| carbs_g | 0.0725 |
| category_Repas/Transformé | 0.0508 |
| cholesterol_mg | 0.0496 |
| fat_g | 0.0484 |
| fiber_g | 0.0390 |
| category_Snack/Transformé | 0.0358 |
| category_Légume | 0.0307 |
| category_Boissons | 0.0229 |
| category_Fruits | 0.0166 |
| category_Desserts | 0.0157 |
| category_Condiments | 0.0135 |
| category_Noix | 0.0105 |
| category_Produits laitiers | 0.0079 |
| category_Repas/Protéines | 0.0077 |
| category_Repas/Végétarien | 0.0073 |
| category_Collation | 0.0064 |
| category_Céréales | 0.0062 |
| category_Protéine/Viande | 0.0056 |
| category_Supplément/Traité | 0.0055 |
| category_Céréales/transformées | 0.0054 |
| category_Farine/Légumineuse | 0.0053 |
| category_Repas/Fruits | 0.0037 |
| category_Boissons/produits laitiers-Alt | 0.0035 |
| category_Féculents | 0.0034 |
| category_Condiment/Laiterie | 0.0034 |
| category_Supplément | 0.0033 |
| category_Protéines/Transformées | 0.0033 |
| category_Repas/Légumes | 0.0030 |
| category_Boissons/produits laitiers | 0.0029 |
| category_Condiment/Transformé | 0.0027 |
| category_Protéine/Poisson | 0.0025 |
| category_Repas/Fruits de mer | 0.0024 |
| category_Légumineuse | 0.0023 |
| category_Légume/Condiment | 0.0022 |
| category_Farine/Céréales | 0.0021 |
| category_Protéines/Fruits de mer | 0.0020 |
| category_Céréales/Dessert | 0.0019 |
| category_Légumes/Transformés | 0.0015 |
| category_Protéiné/Végétarien | 0.0010 |
| category_Repas/Soupe | 0.0010 |
| category_Viande | 0.0007 |
| category_Légumes | 0.0007 |
| category_Repas/Pâtes | 0.0006 |
| category_Repas/Riz | 0.0006 |
| category_Repas | 0.0004 |
| category_Protéine | 0.0002 |
| category_Repas/Poisson | 0.0001 |
| category_Oeufs | 0.0000 |
| category_1 tasse) | 0.0000 |
| category_4oz) | 0.0000 |
| category_Boisson/Repas | 0.0000 |
| category_Collation/Apéritif | 0.0000 |
| category_Collation/Dessert | 0.0000 |
| category_Poisson | 0.0000 |
| category_Produits laitiers/Desserts | 0.0000 |
| category_Protéines/Laitiers | 0.0000 |
| category_Repas/Viande | 0.0000 |
| category_crus) | 0.0000 |
| category_dans le bouillon) | 0.0000 |
| category_jaune) | 0.0000 |
| category_autre | 0.0000 |

## 5. Artefact

Modèle sérialisé : `app/contexts/nutrition/data/meal_type_model.joblib`
Catégories connues : `app/contexts/nutrition/data/meal_type_categories.json`
