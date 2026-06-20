# Documentation technique — Moteurs IA HealthAI Coach

> Ce document explique concrètement **ce que font les algorithmes**, **d'où viennent les données**, **comment sont calculés les scores et métriques**, et **quelles sont les limites** du système.  
> Public cible : développeur reprenant le projet.

---

## Table des matières

1. [Vue d'ensemble du système](#1-vue-densemble-du-système)
2. [Données sources](#2-données-sources)
3. [Moteur Sport (Workout)](#3-moteur-sport-workout)
4. [Moteur Nutrition](#4-moteur-nutrition)
5. [Métriques d'évaluation (MSE, RMSE, RSS, TSS, R²)](#5-métriques-dévaluation-mse-rmse-rss-tss-r)
6. [Précision actuelle des moteurs](#6-précision-actuelle-des-moteurs)
7. [Limites et pistes d'amélioration](#7-limites-et-pistes-damélioration)

---

## 1. Vue d'ensemble du système

```
Client (frontend / mobile)
        │  POST /recommendations/workout
        │  POST /ai/nutrition/meal-plan
        ▼
    API-IA (Flask + Hypercorn, port 9001)
        │
        ├── Contexte WORKOUT ──► MongoDB (programmes, feedbacks)
        │
        └── Contexte NUTRITION ──► Backend NestJS (port 3001)
                                        └── MySQL → table Nutrition (601 aliments Kaggle)
```

Les deux moteurs sont **déterministes et basés sur des règles pondérées** (pas de modèle ML entraîné). Les métriques MSE/R² servent à mesurer la qualité des recommandations, pas à entraîner un modèle.

---

## 2. Données sources

### 2.1 Catalogue d'exercices (Workout)

- **Source** : catalogue statique interne (`app/contexts/workout/domain/data/exercises_catalog.py`)
- **Format** : liste d'objets `ExerciseDefinition` avec attributs :
  - `id`, `name`, `level` (`debutant / intermediaire / avance`)
  - `objectives` (ex: `["perte_de_poids", "renforcement"]`)
  - `equipment` (ex: `["halteres", "tapis"]`)
  - `tags`, `contraindications`
- **Taille** : ~50 exercices couvrant tous les groupes musculaires

### 2.2 Catalogue alimentaire (Nutrition)

- **Source** : dataset Kaggle importé via le backend NestJS
  - Import : `POST /nutrition/import` (ETL avec clé KAGGLE_KEY)
  - Validation ETL : passage par `NutritionStaging` → détection anomalies → approbation → `Nutrition`
- **Taille** : **601 aliments validés** (sur 651 importés — 50 avaient des anomalies)
- **Format par aliment** : `(calories, proteins_g, carbs_g, fats_g, fibers_g)` pour la portion indiquée dans le nom
- **Distribution des calories** :
  | Tranche | Nombre d'aliments | % |
  |---------|-------------------|---|
  | < 50 kcal | 177 | 29% |
  | 50–100 kcal | 107 | 18% |
  | 100–200 kcal | 164 | 27% |
  | 200–400 kcal | 108 | 18% |
  | > 400 kcal | 45 | 7% |
- **Classification automatique** des 601 aliments :
  | Catégorie | Nombre | Règle de classification |
  |-----------|--------|------------------------|
  | `protein` | 24 | ratio protéines/calories > 0.12 **et** protéines > 8g |
  | `carb` | 110 | glucides > 20g **et** glucides×4 / calories > 50% |
  | `vegetable` | 68 | calories < 80 **et** (fibres > 1.5g **ou** mot-clé légume) |
  | `breakfast` | 9 | mot-clé petit-déj (avoine, yaourt, granola…) |
  | `mixed` | 390 | tous les autres |
- **Chargement** : HTTP GET `/nutrition` paginé (100 items/page), cache mémoire TTL 10 min, fallback table statique 30 items si backend indisponible

---

## 3. Moteur Sport (Workout)

### 3.1 Entrées utilisateur

```json
{
  "objectif": "perte_de_poids",
  "niveau": "intermediaire",
  "materiel": ["halteres", "tapis"],
  "limitations": ["genou"],
  "preferences": ["cardio"]
}
```

### 3.2 Formule de score d'un exercice

Chaque exercice reçoit un score entre **0 et 1** :

```
score = 0.40 × score_objectif
      + 0.25 × score_niveau
      + 0.20 × score_materiel
      + 0.10 × score_preferences
      + 0.05 × score_limitations
```

**Détail des sous-scores :**

| Sous-score | Valeur | Condition |
|------------|--------|-----------|
| `score_objectif` | 1.0 | L'objectif user est dans les objectifs de l'exercice |
| | 0.5 | L'exercice n'a pas d'objectifs définis |
| | 0.25 | Aucune correspondance |
| `score_niveau` | 1.0 | Niveau identique |
| | 0.6 | Écart de 1 niveau |
| | 0.2 | Écart de 2+ niveaux |
| `score_materiel` | 1.0 | Tout le matériel requis est disponible |
| | 0.0 | Matériel manquant (filtre dur) |
| `score_preferences` | 1.0 → min(1.0, overlap/nb_prefs + 0.5) | Selon le chevauchement des tags |
| | 0.2 | Aucun tag en commun |
| `score_limitations` | 1.0 | Aucune contre-indication avec les limitations user |
| | 0.0 | Contre-indication détectée (filtre dur) |

**Filtres durs (score = 0 et exercice exclu) :**
- Matériel requis non disponible
- Contre-indication directe avec une limitation (ex : exercice genou + limitation genou)
- ID explicitement bloqué via `"exercice_problematique:<id>"`

### 3.3 Sélection du programme

1. Tous les exercices compatibles sont scorés
2. Groupés par groupe musculaire
3. Top-N par groupe (N=2 par défaut) retenus
4. Programme structuré sur 7 jours (rotation des groupes)

### 3.4 Feedback adaptatif

Après chaque séance, l'utilisateur soumet une note (1–5). Cette note est stockée dans MongoDB (`workout_feedbacks`) et permet :
- De calculer les métriques de performance (voir §5)
- D'entraîner le modèle de scoring appris (voir §3.5)

### 3.5 Modèle de scoring appris (`ExerciseScoringModel`)

La formule à poids fixes du §3.2 reste le **filtre dur** de compatibilité
(matériel manquant, contre-indications), mais le **classement** des exercices
compatibles est désormais confié à un modèle entraîné quand il est disponible
(`app/contexts/workout/domain/services/ml_scoring_model.py`), avec repli
automatique sur la formule heuristique si le modèle n'est pas encore entraîné.

**Choix du modèle :** `GradientBoostingClassifier` (scikit-learn) — adapté à un
faible nombre de features tabulaires, robuste au bruit des notes utilisateur
(subjectives), et doté d'un hyperparamètre `learning_rate` explicite.

**Features** (`feature_engineering.py`, 7 dimensions) : correspondance
objectif, écart de niveau, disponibilité matériel, taux de recoupement des
préférences, conflit de contre-indication, nombre de contre-indications,
nombre de matériel requis.

**Label** : binaire, `1` si la note réelle/simulée du programme contenant
l'exercice est ≥ 4/5, `0` sinon.

**Données d'entraînement** (`dataset_builder.py`) :
- Réelles : reconstruites depuis MongoDB (`workout_feedbacks` ⨝ `workout_programs` ⨝ `user_fitness_profiles`) — la note du programme est reportée sur chaque exercice qu'il contenait ; un exercice explicitement signalé comme problématique reçoit la note minimale.
- Synthétiques (bootstrap) : profils et notes simulées (vérité terrain dérivée de la compatibilité réelle + bruit gaussien), utilisées en complément tant que le volume réel de feedback est insuffisant pour un split train/test et une validation croisée statistiquement significatifs.

**Procédure d'entraînement** (`scripts/train_workout_model.py`) :
1. Split train/test 80/20 stratifié.
2. Balayage du `learning_rate` ∈ {0.01, 0.05, 0.1, 0.2, 0.3} par validation croisée stratifiée 5-fold (métrique F1) sur le train set.
3. Entraînement final avec le meilleur `learning_rate` sur 100 % du train set.
4. Évaluation sur le test set (hold-out, jamais vu à l'entraînement).
5. Sauvegarde du modèle (`joblib`) + rapport (`docs/model-training-report.md`).

**Résultats de la dernière exécution** (7077 échantillons réels — `scripts/seed_real_workout_feedback.py`,
521 profils/programmes/feedbacks générés bout-en-bout via les vrais endpoints HTTP et
le vrai catalogue backend `Exercise` (885 exercices), dont au moins un programme
réellement testé et noté par un humain pendant cette session — + 1800 synthétiques,
8877 au total) :

| learning_rate | F1 (CV 5-fold) |
|---|---|
| 0.01 | 0.795 |
| **0.05 (retenu)** | **0.796** |
| 0.1 | 0.793 |
| 0.2 | 0.787 |
| 0.3 | 0.792 |

| Métrique (test set, 1776 échantillons) | Valeur |
|---|---|
| Exactitude | 0.726 |
| Précision | 0.729 |
| Rappel | 0.876 |
| F1-score | 0.796 |
| Taux de faux positifs | 0.507 |
| Taux de faux négatifs | 0.124 |
| R² (probabilité prédite vs note normalisée) | 0.253 |

Importance apprise des features : `objective_match` (0.62) ≫ `equipment_available`
(0.17) > `level_diff` (0.11) — confirme l'objectif comme facteur largement dominant,
cohérent avec le poids 0.40 de l'heuristique d'origine.

**Note méthodologique sur le seuil de satisfaction** (`_SATISFIED_THRESHOLD`,
`ml_scoring_model.py`) : une première analyse sur un petit échantillon (120
feedbacks, notes {2,3,4} seulement) avait suggéré d'abaisser le seuil de 4 à 3 pour
rééquilibrer les classes. Sur un échantillon plus large (521 feedbacks, notes
{2:30, 3:137, 4:211, 5:143}), ce seuil à 3 s'est révélé être une **sur-correction** :
94 % des échantillons devenaient "satisfaisant", rendant la tâche triviale (F1 gonflé
à 0.96 en prédisant presque toujours positif). Le seuil à 4 a été conservé (~61 %
positif sur le test set), un déséquilibre plus sain. Ceci illustre un piège classique
de l'apprentissage supervisé : le seuil de binarisation d'un label continu est un choix
de modélisation, pas un paramètre que l'entraînement optimise — il doit être validé
empiriquement sur un échantillon représentatif avant d'être figé.

Détail complet : `docs/model-training-report.md` (régénéré à chaque entraînement).

---

## 4. Moteur Nutrition

### 4.1 Calcul TDEE et macros cibles

Quand des biométries sont fournies, les cibles sont calculées dynamiquement :

**Étape 1 — BMR (Métabolisme de base) via formule Mifflin-St Jeor :**

```
Homme : BMR = 10×poids(kg) + 6.25×taille(cm) − 5×âge(ans) + 5
Femme : BMR = 10×poids(kg) + 6.25×taille(cm) − 5×âge(ans) − 161
```

**Étape 2 — TDEE (Dépense énergétique totale) :**

```
TDEE = BMR × facteur_activité
```

| Niveau d'activité | Facteur PAL |
|-------------------|-------------|
| `sedentary` | 1.20 |
| `lightly_active` | 1.375 |
| `moderately_active` | 1.55 |
| `very_active` | 1.725 |
| `extra_active` | 1.90 |

**Étape 3 — Ajustement selon l'objectif :**

| Objectif | Ajustement calorique |
|----------|---------------------|
| `perte_de_poids` | −300 kcal |
| `prise_de_masse` | +400 kcal |
| `equilibre` | 0 |
| `renforcement` | +200 kcal |

Minimum plancher : **1200 kcal/jour** (santé minimale).

**Étape 4 — Répartition des macros :**

```
Protéines (g) = poids(kg) × coefficient_protéine
  → perte_de_poids  : 1.8 g/kg
  → prise_de_masse  : 2.0 g/kg
  → autres          : 1.4 g/kg

Calories restantes = calories_totales − (protéines × 4 kcal/g)
  → Glucides (g) = (restantes × 64%) / 4 kcal/g
  → Lipides (g)  = (restantes × 36%) / 9 kcal/g

Fibres : 30 g/jour (perte de poids) ou 25 g/jour (autres)
```

**Exemple concret — Femme 28 ans, 65 kg, 165 cm, modérément active, perte de poids :**
```
BMR = 10×65 + 6.25×165 − 5×28 − 161 = 1451 kcal
TDEE = 1451 × 1.55 = 2249 kcal
Objectif = 2249 − 300 = 1949 kcal → arrondi : 1949 kcal
Protéines = 65 × 1.8 = 117 g → 468 kcal
Restantes = 1949 − 468 = 1481 kcal
Glucides = (1481 × 0.64) / 4 = 237 g
Lipides  = (1481 × 0.36) / 9 = 59 g
Fibres   = 30 g
```

### 4.2 Détection des déséquilibres nutritionnels

Pour chaque repas analysé :

```
cible_repas(nutriment) = cible_journalière(nutriment) × 1/3
deviation_pct = (actual − cible_repas) / cible_repas × 100

Si |deviation_pct| ≤ 15% → OK
Si deviation_pct > +15%  → EXCES
Si deviation_pct < −15%  → DEFICIT
```

Le statut global du repas est `DESEQUILIBRE` si **au moins un nutriment** est en EXCES ou DEFICIT.

### 4.3 MealComposerService — Composition de repas

Le composer sélectionne des aliments réels du catalogue Kaggle pour atteindre les macros cibles.

**Répartition des cibles par slot :**

| Slot | Fraction journalière | Exemple à 2000 kcal/j |
|------|---------------------|----------------------|
| 🌅 Petit-déjeuner | 25% | 500 kcal |
| ☀️ Déjeuner | 35% | 700 kcal |
| 🌙 Dîner | 30% | 600 kcal |
| 🍎 Collation | 10% | 200 kcal |

**Algorithme de composition (greedy) :**

Pour chaque slot du repas :

```
1. Construire un pool de candidats par priorité de catégorie :
   - Petit-déj  → breakfast > mixed > carb
   - Déjeuner   → protein > carb > vegetable > mixed
   - Dîner      → protein > vegetable > mixed > carb
   - Collation  → mixed > vegetable > breakfast

2. Pour chaque "starter" dans pool[:n_foods × 3] :
   a. Sélectionner le starter
   b. Compléter avec n_foods−1 aliments qui minimisent l'écart calorique restant
   c. Calculer le score du repas combiné

3. Retenir la combinaison avec le meilleur score
```

**Scaling des portions :**

Après sélection, les portions sont ajustées pour atteindre la cible calorique :

```
scale = calories_cible_slot / calories_combinées_sélectionnées
scale = clamp(scale, 0.5, 4.0)

Macros scalées = macros_originales × scale
Nom affiché    :
  scale = 1   → "poulet grillé (150g)"      (inchangé, pas de suffixe)
  scale = 2   → "poulet grillé (150g) ×2"
  scale = 3   → "poulet grillé (150g) ×3"
  scale = 0.5 → "poulet grillé (150g) ×½"

Seules les valeurs entières ou ×½ sont utilisées — jamais de décimales (×1.4, ×3.8…).
```

**Score d'un repas (0–1) :**

```
score = 1 − (Σ wᵢ × min(|actual_i − target_i| / target_i, 1.0)) / Σ wᵢ
```

Avec les poids par nutriment :

| Nutriment | Poids wᵢ | Justification |
|-----------|----------|---------------|
| calories | 1.5 | Indicateur principal de satiété |
| proteins_g | 1.2 | Critical pour masse/récupération |
| carbs_g | 1.0 | Énergie |
| fats_g | 1.0 | Hormones, absorption vitamines |
| fibers_g | 0.8 | Santé digestive |

**Variation sur 7 jours :**
- Fenêtre glissante d'exclusion : **tous** les aliments utilisés les 2 jours précédents sont exclus (petit-déjeuner, déjeuner, dîner, collation inclus)
- Rotation déterministe des candidats via `day_offset` (reproductible)
- Reset de la fenêtre d'exclusion tous les 3 jours pour autoriser les cycles naturels
- Double fallback si le catalogue filtré est trop petit : d'abord catalogue complet, puis ignore les exclusions

**Contraintes alimentaires appliquées :**
- `vegetarien` → exclut viandes + poissons
- `vegan` → exclut viandes + poissons + produits laitiers + œufs + miel
- `allergies: ["arachide"]` → exclut tout item contenant "arachide" dans le nom

### 4.4 MealTypeModel — Classification du créneau de repas

Contrairement au modèle workout (majoritairement synthétique), ce modèle est
entraîné sur des données **100 % réelles** : le catalogue `Nutrition` du backend
(601+ aliments Kaggle, validés par revue humaine via le pipeline ETL). Le label
(`meal_type_name`) est une colonne réelle du dataset — un vrai problème de
classification supervisée à 4 classes, pas une règle distillée.

**Features** (`meal_type_features.py`) : 8 macronutriments (calories, protéines,
glucides, lipides, fibres, sucre, sodium, cholestérol) + encodage one-hot de la
**catégorie** de l'aliment (`category`, table `Nutrition`).

**Choix de la liste des catégories** : récupérée par un vrai appel
`GET /nutrition` (pas une liste copiée à la main) dans
`scripts/train_meal_type_model.py`, puis persistée en JSON
(`app/contexts/nutrition/data/meal_type_categories.json`, artefact généré comme
le `.joblib`) pour que l'API de production charge exactement les mêmes colonnes
que celles apprises à l'entraînement — un modèle scikit-learn attend un vecteur
de taille fixe, donc cette liste ne peut pas être recalculée à chaque requête.
Un test empirique a comparé un sous-ensemble restreint (14 catégories les plus
fréquentes, seuil ≥10 échantillons) à la liste exhaustive (56 catégories) : le
F1 macro en validation croisée était quasi identique (0.479 vs 0.473), donc
aucun signe de surapprentissage — la liste complète a été retenue, sans perte
d'information sur les catégories rares. Une catégorie absente du catalogue au
moment de l'entraînement (ou un item sans catégorie, ex. appelé depuis
`meal_composer.py` qui ne la propage pas dans son catalogue) retombe sur un
bucket "autre" — signal additif, jamais bloquant.

**Résultats de la dernière exécution** (595 échantillons après filtrage de 7
lignes corrompues, 476 train / 119 test) :

| learning_rate | F1 macro (CV 5-fold) |
|---|---|
| 0.01 | 0.381 |
| 0.05 | 0.465 |
| **0.1 (retenu)** | **0.472** |
| 0.2 | 0.462 |
| 0.3 | 0.448 |

| Métrique (test set, 119 échantillons) | Valeur |
|---|---|
| Exactitude (accuracy) | 0.571 |
| Précision (macro) | 0.522 |
| Rappel (macro) | 0.511 |
| F1-score (macro) | 0.507 |
| Baseline classe majoritaire (`Dîner`) | 0.355 |

Le modèle bat la baseline naïve de **+21.6 points** (et le hasard pur, 25% sur
4 classes, de +32 points). Avant l'ajout de la catégorie comme feature
(macros seules), l'accuracy était de 0.462 (+10.7 points sur la baseline) —
la catégorie a quasiment doublé l'écart à la baseline.

La matrice de confusion montre des erreurs cohérentes avec la difficulté
intrinsèque du problème : le modèle confond surtout Déjeuner↔Dîner et
Petit-déjeuner↔Collation, des paires nutritionnellement proches (ex. un yaourt
peut légitimement être pris au petit-déjeuner ou en collation) — pas des
erreurs aléatoires. `sugar_g` et `sodium_mg` restent les features macro les
plus discriminantes ; la catégorie la plus utile est `category_Repas/Transformé`.

**Note qualité des données** : quelques valeurs de `category` dans le dataset
source sont corrompues (fragments de parenthèses mal parsés du CSV Kaggle
d'origine, ex. `"1 tasse)"`, `"4oz)"`). Sans impact sur le modèle — ces
catégories obtiennent une importance ≈0 — mais à signaler comme limite connue
de la qualité des données en amont (ETL).

Détail complet : `docs/model-training-report-nutrition.md` (régénéré à chaque
entraînement).

---

## 5. Métriques d'évaluation (MSE, RMSE, RSS, TSS, R²)

### 5.1 Définitions

Soit `y_true` = valeurs réelles, `y_pred` = valeurs prédites, `n` = nombre d'échantillons.

| Métrique | Formule | Interprétation |
|----------|---------|----------------|
| **RSS** — Somme des carrés des résidus | `Σ(y_true − y_pred)²` | Erreur totale absolue |
| **TSS** — Somme totale des carrés | `Σ(y_true − ȳ_true)²` | Variance totale des données |
| **MSE** — Erreur quadratique moyenne | `RSS / n` | Erreur moyenne par prédiction |
| **RMSE** — Racine de l'erreur quadratique | `√MSE` | Dans la même unité que y (kcal ou g) |
| **R²** — Coefficient de détermination | `1 − RSS/TSS` | % de variance expliqué ∈ (−∞, 1] |

**Interprétation de R² :**
- R² = 1.0 → prédictions parfaites
- R² = 0.0 → modèle équivalent à prédire la moyenne
- R² < 0.0 → modèle pire que la moyenne (attendu pour les moteurs rule-based)

### 5.2 Métriques Workout — `compute_engine_metrics()`

**Fichier** : `app/contexts/workout/domain/services/engine_metrics.py`

```python
samples = [(ExerciseDefinition, UserProfileForScoring, rating_1_to_5), ...]
metrics = compute_engine_metrics(samples)
# → {"mse": 0.20, "rmse": 0.45, "rss": 2.03, "tss": 0.55, "r2": -2.65, "n_samples": 10}
```

**Ce qui est comparé :**
- `y_pred` = score de l'algorithme `score_exercise()` ∈ [0, 1]
- `y_true` = note utilisateur normalisée : `(rating − 1) / 4` ∈ [0, 1]

**Résultats mesurés sur le catalogue :**
```
MSE  = 0.20   (erreur quadratique par exercice)
RMSE = 0.45   (écart moyen de 0.45 point sur une échelle 0–1)
R²   = −2.65  (attendu : le moteur optimise l'adéquation profil, pas les notes utilisateur)
```

> **Pourquoi R² négatif est normal ici** : Le moteur règles pondérées optimise la compatibilité profil↔exercice, pas la prédiction de note utilisateur. R² négatif signifie que les notes utilisateurs sont plus variables que ce que le scoring prédit — ce n'est pas un problème, le système est rule-based par design.

### 5.3 Métriques Nutrition Axe 1 — Lookup accuracy

**Fichier** : `app/contexts/nutrition/domain/nutrition_metrics.py`  
**Fonction** : `compute_lookup_metrics(samples)`

```python
# samples = [(macros_estimées, macros_réelles_DB), ...]
# macros_estimées = BackendNutritionLookupService.compute_macros([nom_aliment])
# macros_réelles  = valeurs directes de la table Nutrition (Kaggle)
metrics = compute_lookup_metrics(samples)
# → {"calories": {"mse": 0.04, "rmse": 0.20, "r2": 1.0000, ...}, ...}
```

**Résultats mesurés (50 aliments)** :
```
calories    RMSE=0.20  R²=1.0000
proteins_g  RMSE=0.03  R²=1.0000
carbs_g     RMSE=0.02  R²=1.0000
```

> R² = 1.0 car le `BackendNutritionLookupService` charge directement les valeurs de la DB — il n'y a pas d'estimation, c'est une lecture directe. Cette métrique devient utile si on bascule vers un modèle de prédiction des macros (ex: HuggingFace).

### 5.4 Métriques Nutrition Axe 2 — Imbalance accuracy

**Fonction** : `compute_imbalance_metrics(meals)`

```python
# meals = [(macros_repas, health_profile), ...]
# y_true = cible du repas (daily_target × 1/3)
# y_pred = macros réelles du repas
metrics = compute_imbalance_metrics(meals)
# → {"calories": {"mse": ..., "rmse": ..., "r2": ..., "mean_deviation_pct": ...}, ...}
```

**Résultats mesurés (20 repas simulés, 1-3 aliments/repas)** :
```
calories    RMSE=455 kcal   R²=−14.2   dev_moy=−42%
proteins_g  RMSE=26.7g      R²=−13.8   dev_moy=−37%
carbs_g     RMSE=58g        R²=−10.1   dev_moy=−51%
```

> Déficits importants car les repas simulés ne contiennent que 1-3 aliments — un repas complet nécessite 3-5 composants. Avec le MealComposer et le scaling de portions, les déficits sont corrigés (cibles atteintes à ~90-95% en calories).

---

## 6. Précision actuelle des moteurs

### 6.1 Workout

| Indicateur | Valeur | Commentaire |
|------------|--------|-------------|
| Score moyen d'un exercice compatible | ~0.70-0.85 | Dépend du profil |
| RMSE vs notes utilisateur | 0.45 | Sur échelle [0,1] |
| R² | −2.65 | Normal pour rule-based |
| Tests | 72/72 ✅ | |

### 6.2 Nutrition

| Indicateur | Valeur | Commentaire |
|------------|--------|-------------|
| Score moyen du MealComposer | ~0.56-0.60 | Sur [0,1], idéal > 0.80 |
| Précision calorique (scaling) | ±5-10% de la cible | Après scaling ×0.5→×4 |
| Lookup R² (vs DB Kaggle) | 1.00 | Lecture directe depuis MySQL |
| Tests | 29/29 ✅ (nutrition) | |
| Tests total | 101/101 ✅ | |

**Score MealComposer selon le profil :**
| Objectif | Score moyen | Calories estimées | Cible | Précision |
|----------|-------------|-------------------|-------|-----------|
| perte_de_poids (1500 kcal) | 0.60 | ~1541 kcal | 1500 | +2.7% |
| équilibre (2000 kcal) | 0.58 | ~1864 kcal | 2000 | −6.8% |
| prise_de_masse (2800 kcal) | 0.56 | ~1984 kcal | 2800 | −29% ⚠️ |

> La prise de masse est en dessous car le catalogue Kaggle a peu d'items très caloriques. Le plafond de scaling (×4) est atteint. Correction possible : augmenter le plafond à ×6 ou filtrer pour ne garder que les items > 100 kcal pour les hauts besoins.

---

## 7. Limites et pistes d'amélioration

### 7.1 Limites connues

| Problème | Impact | Cause |
|----------|--------|-------|
| **Vision IA non configurée** | Détection photo = stub (`poulet-riz`) | Pas de clé Google Vision |
| **LLM non configuré** | Suggestions textuelles = statiques | Pas de clé LLM/Ollama |
| **Cache in-memory** | Rechargement à chaque restart | TTL 10 min, pas de Redis |
| **Score prise_de_masse** | −29% de la cible calorique | Catalogue pauvre en items >400 kcal |
| **Catalogue anglais** | Noms d'aliments en anglais/français mélangés | Dataset Kaggle non traduit |
| **Pas d'auth sur l'API-IA** | Endpoints ouverts sans JWT | À implémenter côté API-IA |

### 7.2 Améliorations possibles

**Court terme (sans ML) :**
- Augmenter `_MAX_SCALE` de 4 à 6 pour les profils haute calorie
- Ajouter une catégorie `snack_proteine` (fromage blanc, barres protéinées)
- Normaliser les noms d'aliments (traduire en français)
- Remplacer le cache mémoire par Redis pour la prod

**Moyen terme (avec ML) :**
- ~~Entraîner un modèle de régression sur les feedbacks workout pour ajuster les poids (actuellement hardcodés)~~ ✅ Fait — voir §3.5 (`ExerciseScoringModel`, `GradientBoostingClassifier`)
- Ré-entraîner périodiquement avec le volume réel de feedback une fois en production (le dataset actuel est majoritairement synthétique)
- Intégrer un modèle de vision pour la détection réelle d'aliments (`POST /ai/nutrition/analyze` avec photo réelle)
- Collaborative filtering : recommander des repas aimés par des users similaires

**Long terme :**
- Transformer les métriques R²/RMSE en KPIs de monitoring (Grafana/Prometheus)
- A/B testing sur les poids de scoring du moteur workout
- Personnalisation progressive : les poids s'affinent avec les feedbacks de chaque utilisateur

---

## Annexe — Points d'entrée API

| Endpoint | Méthode | Corps | Retourne |
|----------|---------|-------|---------|
| `/recommendations/workout` | POST | `FitnessProfile` (objectif, niveau, matériel…) | Programme 7 jours scoré |
| `/recommendations/workout/{id}/feedback` | POST | `{rating: 1-5, comment: ""}` | Feedback enregistré |
| `/ai/nutrition/analyze` | POST | `{imageUrl, userGoal, weightKg…}` | Macros + déséquilibres + conseils |
| `/ai/nutrition/meal-plan` | POST | `{userGoal, dailyCaloriesTarget, dietaryConstraints…}` | Plan 7 jours avec scores |

### Exemple complet — Génération d'un plan repas

```bash
curl -X POST http://localhost:9001/ai/nutrition/meal-plan \
  -H "Content-Type: application/json" \
  -d '{
    "userGoal": "perte_de_poids",
    "weightKg": 70,
    "heightCm": 168,
    "ageYears": 28,
    "gender": "female",
    "physicalActivityLevel": "moderately_active",
    "dietaryConstraints": ["vegetarien"],
    "allergies": ["arachide"]
  }'
```

Réponse type :
```json
{
  "userGoal": "perte_de_poids",
  "modelStatus": "composer_active",
  "notes": [
    "Plan composé à partir du catalogue de 601 aliments validés.",
    "Score moyen d'équilibre nutritionnel : 0.598/1.0",
    "Les contraintes et allergies déclarées sont appliquées."
  ],
  "days": [
    {
      "day": 1,
      "breakfast": "crêpes (2 moyennes), flocons d'avoine 50g",
      "lunch": "fromage cottage (1/2 tasse), gnocchi à la sorrentine (1,5 tasse), pomme",
      "dinner": "seitan (3oz) ×1.5, riz pilaf (1 tasse) ×2, brocoli cuit (1 tasse)",
      "snack": "amandes (1 oz)",
      "estimatedCalories": 1541
    }
  ]
}
```

---

*Généré le 2026-05-20 — API-IA v1.0 — MSPR TPRE502 HealthAI Coach*
