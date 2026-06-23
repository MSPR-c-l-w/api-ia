# Documentation technique complète — Micro-service `api-ia`
## HealthAI Coach — MSPR TPRE502

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Système de recommandations nutritionnelles](#3-système-de-recommandations-nutritionnelles)
4. [Moteur de recommandations sportives](#4-moteur-de-recommandations-sportives)
5. [Entraînement des modèles ML](#5-entraînement-des-modèles-ml)
6. [Preuve d'entraînement pour le jury](#6-preuve-dentraînement-pour-le-jury)
7. [Infrastructure & persistence](#7-infrastructure--persistence)
8. [Authentification & sécurité](#8-authentification--sécurité)
9. [Endpoints API](#9-endpoints-api)
10. [Gestion des erreurs](#10-gestion-des-erreurs)
11. [Réentraînement automatique](#11-réentraînement-automatique)
12. [Tests](#12-tests)
13. [Configuration](#13-configuration)
14. [Chiffres clés](#14-chiffres-clés)

---

## 1. Vue d'ensemble

`api-ia` est un **micro-service Python** indépendant du backend principal (NestJS), conçu pour héberger les deux moteurs IA de la plateforme HealthAI Coach :

| Moteur | Technologie principale | Stockage |
|---|---|---|
| Recommandations sportives | GradientBoostingClassifier (scikit-learn) | MongoDB |
| Recommandations nutritionnelles | Vision IA + GradientBoostingClassifier + LLM | MongoDB + catalogue Kaggle |

**Pourquoi un micro-service séparé ?**
Le cahier des charges impose que le moteur de recommandation soit développé **séparément de l'application principale** pour permettre son évolution future et sa scalabilité indépendante. Les modèles ML peuvent être réentraînés et déployés sans toucher au backend NestJS.

**Stack technique :**

| Couche | Technologie |
|---|---|
| Framework web | Flask 3.1 (ASGI via Hypercorn) |
| ML | scikit-learn (GradientBoostingClassifier), joblib |
| Base de données | MongoDB via Motor (async) |
| Validation | Pydantic v2 |
| Vision IA | Ollama (llava/moondream) + Google Vision (fallback) |
| LLM | Ollama NLP (génération plans de repas) |
| Planification | APScheduler (réentraînement hebdomadaire) |
| Tests | pytest + pytest-cov (329 tests, 93,7% couverture) |

---

## 2. Architecture

### 2.1 Découpage en couches (Clean Architecture + DDD)

Le projet est structuré en **bounded contexts** (DDD) avec une séparation stricte des couches :

```
api-ia/
├── app/
│   ├── main.py                          # Point d'entrée Flask + lifespan ASGI
│   ├── config.py                        # Pydantic Settings (variables d'env)
│   ├── contexts/
│   │   ├── workout/                     # Bounded context : sport
│   │   │   ├── domain/                  # Entités, value objects, services métier
│   │   │   │   ├── entities/            # WorkoutProgram, UserFitnessProfile, WorkoutFeedback
│   │   │   │   ├── value_objects/       # ExerciseDefinition, UserProfileForScoring
│   │   │   │   ├── services/
│   │   │   │   │   ├── ml_scoring_model.py      # ExerciseScoringModel (GradientBoosting)
│   │   │   │   │   ├── feature_engineering.py   # Extraction des 7 features numériques
│   │   │   │   │   ├── recommendation_engine.py # Scoring + filtrage exercices
│   │   │   │   │   ├── weekly_planner.py        # Génération programme 7 jours
│   │   │   │   │   └── dataset_builder.py       # Construction dataset d'entraînement
│   │   │   │   └── data/
│   │   │   │       ├── exercises_catalog.py             # Catalogue 80+ exercices
│   │   │   │       └── exercise_scoring_model.joblib    # Modèle ML sérialisé
│   │   │   ├── application/use_cases/
│   │   │   │   ├── create_workout_program.py    # UC : générer + persister programme
│   │   │   │   └── submit_workout_feedback.py   # UC : feedback + adaptation profil
│   │   │   └── infrastructure/
│   │   │       ├── persistence/                 # Repositories MongoDB
│   │   │       └── backend_exercise_lookup.py   # Lookup catalogue backend NestJS
│   │   └── nutrition/                   # Bounded context : nutrition
│   │       ├── domain/
│   │       │   ├── models.py            # VisionDetection, Macros, HealthProfile
│   │       │   ├── services.py          # NutritionImbalanceService
│   │       │   ├── tdee.py              # TdeeCalculator (Mifflin-St Jeor)
│   │       │   ├── meal_type_model.py   # MealTypeModel (GradientBoosting)
│   │       │   └── meal_composer.py     # Composition plan de repas (fallback LLM)
│   │       ├── application/use_cases/
│   │       │   ├── analyze_meal.py      # UC : vision + macros + suggestions
│   │       │   └── generate_meal_plan.py # UC : plan 7 jours personnalisé
│   │       └── infrastructure/
│   │           ├── vision/              # Google Vision + Ollama vision
│   │           ├── llm_provider.py      # Ollama NLP (génération plans)
│   │           ├── mongo_nutrition_lookup.py    # Lookup MongoDB (Kaggle)
│   │           └── nutrition_lookup.py  # Lookup statique offline (100+ aliments)
│   ├── shared/
│   │   ├── domain/
│   │   │   └── model_deployment_guard.py   # Garde-fou : ne déploie que si F1 ≥ ancien
│   │   └── infrastructure/
│   │       ├── database.py              # Connexion Motor MongoDB
│   │       ├── retraining_scheduler.py  # Planificateur APScheduler
│   │       └── collections.py           # Noms collections MongoDB
│   ├── routers/                         # Blueprints Flask
│   │   ├── health.py                    # GET /health
│   │   ├── recommendations.py           # POST /recommendations/workout
│   │   └── nutrition.py                 # POST /ai/nutrition/...
│   ├── dependencies/
│   │   └── api_key.py                   # Décorateur @require_api_key
│   └── presentation/
│       ├── http.py                      # Validation Pydantic + sérialisation
│       ├── exception_handlers.py        # Gestion erreurs Flask
│       └── openapi.py                   # Schéma OpenAPI 3.1 dynamique
├── scripts/
│   ├── train_workout_model.py           # Script entraînement modèle sport
│   └── train_meal_type_model.py         # Script entraînement modèle nutrition
└── tests/
    ├── unit/                            # 310 tests unitaires (aucun service ext.)
    ├── integration/                     # Tests avec MongoDB réel
    └── e2e/                             # Tests stack complète
```

### 2.2 Flux d'une requête

```
Client (backend NestJS ou front)
  │
  ▼
@require_api_key (X-API-Key header — routes protégées uniquement)
  │
  ▼
Router Flask (Blueprint)
  │
  ▼
parse_json() → validation Pydantic DTO
  │
  ▼
Use Case (application/)
  │  orchestration : domain/ + infrastructure/
  ▼
Domain Services (scoring, imbalance, TDEE, LLM, vision...)
  │
  ▼
Repositories MongoDB (Motor async) + Providers externes (Ollama, Google Vision)
  │
  ▼
model_response() → JSON sérialisé → HTTP 200
```

---

## 3. Système de recommandations nutritionnelles

### 3.1 Analyse de photo de repas

**Endpoint :** `POST /ai/nutrition/analyze` (ou `POST /ai/nutrition/analyze-photo` depuis le backend)

**Objectif :** L'utilisateur soumet une photo de son repas. Le système identifie automatiquement les aliments, calcule les macros, détecte les déséquilibres et génère des suggestions personnalisées.

#### Étape 1 — Vision IA (identification des aliments)

Le système utilise une **chaîne de fournisseurs avec fallback automatique** :

```
Ollama Vision (llava / moondream / qwen2.5-vl) — local, gratuit, prioritaire
  │  Si endpoint non configuré ou erreur réseau
  ▼
Google Vision API — cloud
  │  Si endpoint non configuré ou erreur réseau
  ▼
Stub (données de démonstration : poulet + riz, confidence 0.84)
```

**Comment fonctionne Ollama Vision (provider principal) :**

Ollama est un moteur qui fait tourner des **modèles de vision multimodaux** en local sur le serveur (llava, moondream, qwen2.5-vl). Ces modèles sont capables d'analyser une image et de répondre à des questions en langage naturel sur son contenu.

Le système lui envoie l'image + un prompt précis :
```
"Identifie chaque aliment réellement présent dans ce plat.
Réponds UNIQUEMENT en JSON : {"foods":[{"label":"...","confidence":0.0}]}.
Utilise des noms simples en français, au singulier. N'invente aucun aliment."
```

Le modèle retourne par exemple :
```json
{"foods": [
  {"label": "poulet", "confidence": 0.91},
  {"label": "riz basmati", "confidence": 0.88},
  {"label": "brocoli", "confidence": 0.76}
]}
```

**Gestion de l'image :** accepte une URL publique (téléchargée et convertie en base64 avant envoi) ou directement une image en base64. Timeout de téléchargement : 15 secondes.

**Plancher de confiance :** les petits modèles de vision locaux n'émettent pas de scores de confiance bien calibrés — un aliment correctement identifié peut recevoir un score arbitrairement bas. Un plancher minimum de **0.6** est appliqué pour ne pas écarter une détection valide. Le use case filtre ensuite sous **0.5** les détections trop incertaines.

**Maintien en RAM :** le modèle Ollama reste chargé 30 minutes entre deux requêtes (`keep_alive: 30m`). Sur CPU, un rechargement à froid peut prendre plusieurs minutes — ce paramètre évite ce délai sur les requêtes successives.

**Comment fonctionne Google Vision (fallback cloud) :**

Appel HTTP vers l'endpoint Google Vision configuré, avec l'image en URL ou base64. Retourne la même structure `{"foods": [{"label": "...", "confidence": 0.0}]}`. Timeout : 5 secondes. Aucun traitement spécifique — le fournisseur est un adaptateur simple vers l'API externe.

**Résultat commun :** chaque fournisseur retourne une liste de `VisionDetection` :
```python
@dataclass
class VisionDetection:
    label: str        # Ex: "poulet", "riz basmati", "brocoli"
    confidence: float # Score de confiance 0.0 → 1.0
```

**Filtrage post-détection :** les labels non-alimentaires (table, assiette, verre, fourchette...) sont éliminés par une liste de mots-clés. Les détections sous 0.5 de confiance sont écartées.

**Cache :** les résultats vision sont mis en cache **1 heure** par URL d'image — si l'utilisateur soumet deux fois la même photo, le modèle de vision n'est pas rappelé.

#### Étape 2 — Lookup macros

Pour chaque aliment détecté, le système cherche les valeurs nutritionnelles :

```
MongoDB nutrition_foods (600+ aliments Kaggle validés)
  │  Si non trouvé
  ▼
Table statique embarquée (100+ aliments courants)
  │  Si non trouvé
  ▼
Valeurs par défaut estimées (150 kcal, 8g prot, 18g carbs, 5g fats, 1.5g fibres)
```

Le champ `estimated: True` est positionné si les valeurs sont approximées.

#### Étape 3 — Profil santé et cibles caloriques

Le système construit un `HealthProfile` personnalisé selon deux modes :

**Mode biométrique (si données fournies) — Formule Mifflin-St Jeor :**
```
BMR (homme) = 10 × poids_kg + 6.25 × taille_cm − 5 × âge + 5
BMR (femme) = 10 × poids_kg + 6.25 × taille_cm − 5 × âge − 161
TDEE = BMR × PAL (1.2 → 1.9 selon activité)
Calories objectif = TDEE ± ajustement selon goal (−350 kcal perte, +400 kcal masse)
```

**Mode objectif (par défaut) :**

| Objectif | Calories | Protéines | Glucides | Lipides | Fibres |
|---|---|---|---|---|---|
| perte_de_poids | 1700 kcal | 90 g | 180 g | 55 g | 30 g |
| prise_de_masse | 2700 kcal | 130 g | 330 g | 85 g | 25 g |
| equilibre | 2000 kcal | 75 g | 250 g | 70 g | 25 g |

#### Étape 4 — Détection des déséquilibres

Comparaison macros du repas vs 1/3 des cibles quotidiennes (un repas = ~33% de la journée).

**Seuil de tolérance : ±15%**

```
deviation_pct = (actual − target) / target × 100

Si deviation_pct > +15% → EXCES
Si deviation_pct < −15% → DEFICIT
Sinon → OK
```

Exemple de réponse `nutrientDetails` :
```json
{
  "name": "proteins_g",
  "actual": 45.0,
  "target": 25.0,
  "unit": "g",
  "status": "EXCES",
  "deviation_pct": 80.0
}
```

`imbalanceStatus` global :
- `EQUILIBRE` — tous les nutriments dans la tolérance
- `DESEQUILIBRE` — au moins un nutriment hors tolérance

#### Étape 5 — Suggestions LLM

**Cache :** 24 heures par combinaison `(goal + tokens_déséquilibres)`.

```
Ollama NLP (génération de suggestions en français)
  │  Si indisponible
  ▼
Suggestions statiques curées (listes par objectif + type de déséquilibre)
```

Exemple de suggestion générée : *"Votre apport en protéines est élevé — c'est favorable pour la prise de masse. Veillez à maintenir une bonne hydratation."*

---

### 3.2 Génération de plan de repas

**Endpoint :** `POST /ai/nutrition/meal-plan`

**Objectif :** Générer un plan alimentaire complet sur 7 jours, personnalisé selon l'objectif, les allergies, le régime et le budget.

#### Paramètres acceptés

```json
{
  "userId": 42,
  "userGoal": "equilibre",
  "dietaryConstraints": ["vegan", "sans gluten"],
  "allergies": ["arachide", "lactose"],
  "weightKg": 70.0,
  "heightCm": 170.0,
  "ageYears": 28,
  "gender": "female",
  "physicalActivityLevel": "moderately_active",
  "budget": 350.0
}
```

#### Stratégie de génération (3 niveaux)

**Niveau 1 — MealComposer (priorité) :**
Compose 7 jours à partir du **catalogue Kaggle réel** (600+ aliments validés via le pipeline ETL et la revue humaine en back-office). Filtre selon les contraintes alimentaires et les allergies. Optimise le score d'équilibre nutritionnel (R²). Utilise le `MealTypeModel` (GradientBoosting entraîné sur ces mêmes données) pour assigner chaque aliment au bon créneau : petit-déjeuner / déjeuner / dîner / collation. Le budget est pris en compte dans la sélection des aliments.

**Niveau 2 — LLM Ollama (fallback) :**
Activé uniquement si le catalogue MongoDB est indisponible. Appelle Ollama NLP avec un prompt structuré incluant l'objectif, les contraintes, les allergies et les cibles caloriques. Le JSON retourné est validé. La réponse indique explicitement que le catalogue était indisponible (`modelStatus: "llm_active"`).

**Niveau 3 — Stub (dernier recours) :**
Plan hardcodé minimal avec note explicative ("catalogue et LLM indisponibles").

---

### 3.3 Modèle MealTypeModel (classification du type de repas)

Ce modèle est utilisé par le MealComposer pour assigner chaque aliment du catalogue au bon créneau de repas.

**Type :** `GradientBoostingClassifier` (scikit-learn)
**Sérialisation :** `app/contexts/nutrition/data/meal_type_model.joblib`
**Catégories :** `app/contexts/nutrition/data/meal_type_categories.json`

**Entrée (features) :**
- 8 macros : `calories`, `protein_g`, `carbohydrates_g`, `fat_g`, `fiber_g`, `sugar_g`, `sodium_mg`, `cholesterol_mg`
- One-hot encoding du champ `category` (50+ catégories dynamiques issues du catalogue — ex: `category_Légume`, `category_Snack/Transformé`, `category_Boissons`...)

**Pourquoi `name` n'est pas inclus :** le nom de l'aliment pourrait donner un signal utile (ex: "café" → Petit-déjeuner, "biscuit" → Collation), mais avec seulement 595 aliments dans le dataset, le modèle mémoriserait les noms vus à l'entraînement plutôt que de généraliser (overfitting). Un nouvel aliment importé via l'ETL avec un nom inconnu donnerait un signal nul. Exploiter `name` correctement nécessiterait du NLP (TF-IDF, embeddings) — hors scope du projet.

**Sortie :** classe parmi `{Petit-déjeuner, Déjeuner, Dîner, Collation}`

---

## 4. Moteur de recommandations sportives

### 4.1 Génération de programme d'entraînement

**Endpoint :** `POST /recommendations/workout` (protégé X-API-Key)

**Objectif :** Générer un programme d'entraînement hebdomadaire personnalisé sur 7 jours.

#### Paramètres

```json
{
  "userId": 42,
  "objectif": "renforcement",
  "niveau": "intermediaire",
  "materiel": ["haltères", "tapis"],
  "preferences": ["faible impact", "force"],
  "limitations": ["genou"]
}
```

#### Processus de génération

**1. Rotation anti-répétition :**
Récupère les exercices des 2 dernières semaines depuis MongoDB. Ces exercices reçoivent une pénalité de −30% sur leur score pour favoriser la variété.

**2. Scoring de chaque exercice (ExerciseScoringModel) :**
Pour chaque exercice du catalogue, le modèle ML calcule un score de pertinence (probabilité 0–1). Si le modèle n'est pas disponible, une heuristique pondérée prend le relais.

**3. Planification hebdomadaire :**

| Niveau | Jours d'entraînement | Jours de repos |
|---|---|---|
| Débutant | 3 | 4 |
| Intermédiaire | 4 | 3 |
| Avancé | 5 | 2 |
| Athlète | 6 | 1 |

Répartition musculaire : chaque groupe musculaire est sollicité au maximum 2 fois par semaine. Les jours de repos sont intercalés stratégiquement.

**4. Durée estimée par séance :**
Calculée selon le nombre d'exercices × durée estimée (sets × reps × temps de récupération).

#### Catalogue d'exercices

Le moteur utilise en priorité les exercices de la **table `Exercise` du backend NestJS**, importés via le pipeline ETL (source : GitHub JSON, validés en back-office). Le catalogue est récupéré via `GET /exercise` (paginé, cache 10 minutes), puis mappé en `ExerciseDefinition`.

**Fallback :** si le backend est indisponible, un catalogue statique embarqué de 80+ exercices (`exercises_catalog.py`) prend le relais automatiquement.

Chaque exercice est représenté par la structure suivante :

```python
ExerciseDefinition(
    id="pompes",
    name="Pompes",
    muscle_group="pectoraux",
    level="debutant",              # debutant | intermediaire | avance | athlete
    objectives=["renforcement", "prise_de_masse", "performance"],
    equipment=[],                  # Aucun matériel requis
    tags=["sans materiel", "force", "polyarticulaire"],
    contraindications=["epaule", "poignet"]
)
```

---

### 4.2 Système de feedback et adaptation

**Endpoint :** `POST /recommendations/workout/<program_id>/feedback`

**Objectif :** L'utilisateur évalue son programme. Le système adapte son profil et génère les données d'entraînement pour le prochain cycle ML.

#### Paramètres

```json
{
  "rating": 4,
  "tropDifficile": false,
  "tropFacile": false,
  "exercicesProblematiques": ["pompes"]
}
```

#### Adaptations automatiques du profil

À chaque feedback soumis, le `UserFitnessProfile` de l'utilisateur est mis à jour automatiquement selon trois mécanismes :

---

**1. Blocage temporaire des exercices problématiques**

Quand l'utilisateur remonte des `exercicesProblematiques` (ex. : `["pompes", "burpees"]`), chaque exercice reçoit un token de blocage ajouté à son profil :

```
limitations = ["exercice_problematique:pompes", "exercice_problematique:burpees"]
```

Ce token expire automatiquement après **30 jours**. La date d'expiration est stockée dans l'historique :

```json
{
  "type": "temporary_limitation",
  "exerciseIds": ["pompes", "burpees"],
  "expiresAt": "2026-07-20T12:00:00+00:00"
}
```

À chaque nouveau feedback, les tokens expirés sont **nettoyés automatiquement** avant d'en ajouter de nouveaux — l'utilisateur ne reste pas bloqué indéfiniment sur un exercice.

Lors de la génération du programme suivant, le moteur de scoring détecte ces tokens dans `limitations` et attribue un score `limitation_conflict = 1` à ces exercices, ce qui les exclut de facto du programme généré.

---

**2. Progression automatique de niveau**

Quand l'utilisateur coche `tropFacile = true`, le système comptabilise ses feedbacks "trop facile" des 30 derniers jours. Dès le **3ème signal** sur cette fenêtre glissante, le niveau est automatiquement augmenté d'un cran :

```
débutant → intermédiaire → avancé → athlète
```

L'événement est tracé dans l'historique :

```json
{
  "type": "level_adjustment",
  "from": "debutant",
  "to": "intermediaire",
  "reason": "trop_facile_repeated",
  "at": "2026-06-20T12:00:00+00:00"
}
```

Le niveau mis à jour est immédiatement pris en compte dans le prochain programme généré — les exercices proposés seront plus difficiles et la fréquence hebdomadaire augmentée.

---

**3. Historique complet et traçabilité**

Chaque événement est conservé dans `UserFitnessProfile.historique` (liste append-only en MongoDB) :

| Type d'événement | Déclenché par |
|---|---|
| `feedback` | Chaque soumission (rating, difficultés, exercices signalés) |
| `temporary_limitation` | Exercices signalés comme problématiques |
| `level_adjustment` | 3× "trop facile" en 30 jours |

Ce sont les collections MongoDB `workout_feedbacks` et `workout_programs` (pas directement l'historique) qui alimentent le dataset d'entraînement du modèle `ExerciseScoringModel` lors du réentraînement hebdomadaire — voir §5.1.

---

### 4.3 Modèle ExerciseScoringModel

**Type :** `GradientBoostingClassifier` (scikit-learn)
**Sérialisation :** `app/contexts/workout/domain/data/exercise_scoring_model.joblib`
**Hyperparamètres :** `learning_rate=0.05, n_estimators=100, max_depth=3, random_state=42`

#### Features d'entrée (7 features numériques)

| # | Feature | Type | Description |
|---|---|---|---|
| 1 | `objective_match` | 0 / 1 | L'objectif utilisateur est dans les objectifs de l'exercice |
| 2 | `level_diff` | entier | Écart en niveaux (abs) entre utilisateur et exercice |
| 3 | `equipment_available` | 0 / 1 | Tout le matériel requis est disponible |
| 4 | `preference_overlap_ratio` | 0.0–1.0 | Ratio d'intersection tags/préférences utilisateur |
| 5 | `limitation_conflict` | 0 / 1 | Contre-indication active pour cet exercice |
| 6 | `n_contraindications` | float | Nombre total de contre-indications de l'exercice |
| 7 | `n_equipment_required` | float | Nombre d'items de matériel requis |

#### Label de sortie (binaire)

```
satisfait = 1  si note ≥ 4 (sur 5)
satisfait = 0  si note < 4
```

Les exercices signalés comme "problématiques" par l'utilisateur reçoivent automatiquement le label `0`.

---

## 5. Entraînement des modèles ML

### 5.1 Modèle sport — `ExerciseScoringModel`

**Script :** `scripts/train_workout_model.py`
**Déclenchement :** automatique chaque dimanche à 3h UTC — **uniquement si le serveur est en cours d'exécution** et si `ENABLE_RETRAINING_SCHEDULER=true` dans le `.env` (désactivé par défaut). Si le serveur est arrêté à ce moment, l'entraînement n'a pas lieu et n'est pas rattrapé au redémarrage. Sinon, déclenchement manuel : `python scripts/train_workout_model.py`

#### Données utilisées

| Source | Échantillons | Description |
|---|---|---|
| Réels — MongoDB `workout_feedbacks` | **7 077** | Feedbacks ayant transité par les vrais endpoints HTTP et stockés en MongoDB via les vraies entités de domaine. Les notes (rating 1–5) sont majoritairement simulées par `scripts/seed_real_workout_feedback.py` (score de compatibilité profil/exercice + bruit gaussien), faute de volume suffisant de testeurs humains. Au moins un feedback a été fourni par un humain réel avec une note authentique. |
| Synthétiques — bootstrap | **1 800** | 300 profils utilisateurs fictifs créés aléatoirement (objectif, niveau, matériel, limitations tirés au sort), multipliés par 6 exercices réels choisis au hasard dans le catalogue. La note (1–5) de chaque paire `(exercice, profil)` est calculée par une formule de compatibilité pondérée (objectif 35%, niveau 25%, matériel 25%, contre-indications 15%) puis bruitée avec un bruit gaussien (σ=0.12) pour éviter un signal trop parfait. Générés entièrement en mémoire (pas d'appel HTTP, pas de MongoDB). Rôle : compléter le volume de données pour permettre un split 80/20 + cross-validation 5-fold statistiquement solide. |
| **Total** | **8 877** | |
| Train (80%) | 7 101 | Utilisé pour l'entraînement et la cross-validation. Le modèle apprend uniquement sur ces données. |
| Test (20%, hold-out) | 1 776 | Mis de côté dès le début, jamais utilisé pendant l'entraînement ni la cross-validation. Sert uniquement à l'évaluation finale pour mesurer la vraie capacité de généralisation du modèle — c'est-à-dire ses performances sur des données nouvelles, comme en production. Sans ce split, le modèle pourrait mémoriser les données d'entraînement et afficher un score gonflé sans valeur réelle. |

**Origine des données réelles :** les feedbacks MongoDB proviennent de :
1. `scripts/seed_real_workout_feedback.py` — génération d'entités de domaine via les endpoints HTTP réels avec note simulée par compatibilité profil/exercice + bruit aléatoire.
2. Au moins un programme généré et noté par un **humain réel** (endpoints réels, note authentique).

**Catalogue d'exercices utilisé :** le catalogue backend NestJS réel (table `Exercise`, importée via ETL GitHub JSON), pas le fichier statique `exercises_catalog.py` — garantit la cohérence avec les vrais exercices en production.

#### Processus d'entraînement

```
1. Chargement données MongoDB
   └── Jointure : workout_feedbacks ⨝ workout_programs ⨝ user_fitness_profiles

2. Génération données synthétiques
   └── 300 profils aléatoires (objectifs, niveaux, équipements, contraintes)
   └── Score de compatibilité simulé + bruit gaussien → label binaire

3. Fusion réel + synthétique → 8 877 exemples

4. Feature engineering
   └── 7 features numériques par paire (exercice, profil_utilisateur)

5. Split stratifié 80/20
   └── Train set : 7 101 exemples  |  Test set (hold-out) : 1 776 exemples
   └── "Stratifié" = le ratio satisfait/insatisfait est maintenu identique dans
       les deux parties (évite que le test set soit par malchance trop facile ou trop dur)

6. Balayage du learning_rate par cross-validation 5-fold
   └── Le learning_rate contrôle l'intensité des corrections à chaque nouvel arbre
       du GradientBoosting : trop élevé = corrections agressives (risque d'overfitting),
       trop faible = apprentissage lent et sous-optimal.
   └── On teste 5 valeurs candidates : [0.01, 0.05, 0.1, 0.2, 0.3]
   └── Pour chaque valeur, on divise le train set en 5 blocs (folds) et on fait
       5 tours : à chaque tour, 4 blocs servent à entraîner et 1 bloc à évaluer.
       On moyenne les 5 scores F1 obtenus → F1 moyen fiable sans toucher au test set.
   └── 5 valeurs × 5 folds = 25 entraînements au total
   └── La valeur avec le meilleur F1 moyen est retenue (ici : 0.05, F1 = 0.7962)

7. Entraînement final
   └── Meilleur learning_rate (0.05) sur 100% du train set
   └── n_estimators=100 : le modèle construit 100 arbres de décision en séquence,
       chacun corrigeant les erreurs du précédent. La prédiction finale est la
       somme pondérée des 100 arbres. Trop peu → modèle trop simple. Trop → overfitting.
   └── max_depth=3 : chaque arbre peut poser au maximum 3 questions (nœuds) pour
       classer un exemple. Chaque arbre reste intentionnellement simple — c'est
       leur combinaison à 100 qui donne la puissance de prédiction.

8. Évaluation sur test set (hold-out)
   └── Le test set (1 776 exemples) n'a jamais été vu pendant les étapes 6 et 7
       — c'est la seule évaluation qui mesure la vraie capacité de généralisation.
   └── Accuracy (0.7264) : proportion de prédictions correctes toutes classes confondues.
       Sur 1 776 exemples, 72,6% sont bien classés.
   └── Precision (0.7290) : parmi tous les exercices que le modèle prédit "satisfaisants",
       72,9% le sont vraiment. Évite de recommander des exercices inadaptés.
   └── Recall (0.8760) : parmi tous les exercices réellement satisfaisants,
       le modèle en retrouve 87,6%. Évite d'en manquer trop.
   └── F1 (0.7958) : moyenne harmonique de Precision et Recall — métrique principale
       car elle équilibre les deux. Un F1 de 0.80 est solide pour ce type de tâche.
   └── Matrice de confusion : tableau croisant prédictions vs réalité :
         343 vrais négatifs  (insatisfaisant prédit insatisfaisant)
         947 vrais positifs  (satisfaisant prédit satisfaisant)
         352 faux positifs   (insatisfaisant prédit satisfaisant — exercice mal recommandé)
         134 faux négatifs   (satisfaisant prédit insatisfaisant — exercice écarté à tort)
       Le modèle préfère recommander trop que pas assez (recall élevé),
       ce qui est le bon compromis pour une appli de coaching.

9. Déploiement conditionnel (ModelDeploymentGuard)
   └── Si F1_nouveau ≥ F1_ancien → sauvegarde joblib + metrics.json
   └── Sinon → ancien modèle conservé, logs d'alerte

10. Rapport automatique
    └── docs/model-training-report.md (généré automatiquement)
```

#### Résultats réels (rapport du 2026-06-20)

**Balayage learning_rate (CV 5-fold) :**

| learning_rate | F1 moyen | Écart-type |
|---|---|---|
| 0.01 | 0.7949 | 0.007 |
| **0.05** | **0.7962** | 0.0071 |
| 0.1 | 0.7925 | 0.0135 |
| 0.2 | 0.7873 | 0.014 |
| 0.3 | 0.7919 | 0.0158 |

**→ learning_rate retenu : 0.05**

**Performance sur test set (hold-out 1 776 exemples) :**

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | **0.7264** |
| Précision | **0.7290** |
| Rappel (recall) | **0.8760** |
| **F1-score** | **0.7958** |
| R² (proba vs note normalisée) | 0.2534 |
| RMSE | 0.4217 |

**Matrice de confusion :**

| | Prédit non satisfaisant (0) | Prédit satisfaisant (1) |
|---|---|---|
| **Réel non satisfaisant (0)** | 343 (TN) | 352 (FP) |
| **Réel satisfaisant (1)** | 134 (FN) | 947 (TP) |

**Importance des features (apprise par le modèle) :**

L'importance d'une feature mesure sa contribution totale à travers les 100 arbres : à chaque fois que le modèle utilise cette feature pour couper une branche, il mesure de combien ça améliore la prédiction. La somme sur tous les arbres donne l'importance finale. C'est ce que le modèle a **appris seul** à partir des données — pas ce qu'on lui a imposé.

| Feature | Importance | Heuristique fixée à la main (avant ML) | Interprétation |
|---|---|---|---|
| `objective_match` | **0.6199** | 0.40 | Sous-estimé : l'objectif compte bien plus qu'on croyait (62% de la décision) |
| `equipment_available` | **0.1749** | 0.20 | Proche de l'intuition initiale |
| `level_diff` | **0.1094** | 0.25 | Sur-estimé : le niveau compte deux fois moins qu'on pensait |
| `n_contraindications` | 0.0610 | — | Non pris en compte dans l'ancienne heuristique |
| `limitation_conflict` | 0.0154 | 0.05 | Proche |
| `n_equipment_required` | 0.0105 | — | Non pris en compte dans l'ancienne heuristique |
| `preference_overlap_ratio` | 0.0090 | 0.10 | Largement sur-estimé : les préférences comptent très peu en pratique |

> **Ce que ça prouve :** si l'exercice ne correspond pas à l'objectif de l'utilisateur (ex : exercice cardio pour quelqu'un qui veut prendre de la masse), le modèle l'écarte quasi systématiquement peu importe le reste. Le ML a corrigé nos intuitions : le niveau et les préférences comptent beaucoup moins qu'on le fixait à la main, l'objectif beaucoup plus.

---

### 5.2 Modèle nutrition — `MealTypeModel`

**Script :** `scripts/train_meal_type_model.py`
**Déclenchement :** automatique chaque dimanche à 4h UTC — **uniquement si le serveur est en cours d'exécution** et si `ENABLE_RETRAINING_SCHEDULER=true` dans le `.env` (désactivé par défaut). Sinon, déclenchement manuel : `python scripts/train_meal_type_model.py`

#### Données utilisées

**Source :** catalogue réel `Nutrition` du backend NestJS — dataset Kaggle importé via ETL, validé par revue humaine en back-office.

**Accès :** authentification service account (`BACKEND_SERVICE_EMAIL` + `BACKEND_SERVICE_PASSWORD`) → `GET /nutrition` (lecture paginée jusqu'au dernier aliment).

| Classe (meal_type_name) | Échantillons |
|---|---|
| Collation | 166 |
| Dîner | 211 |
| Déjeuner | 136 |
| Petit-déjeuner | 82 |
| **Total (après filtrage)** | **595** |
| Train (80%) | 476 |
| Test (20%, hold-out) | 119 |

> Le label `meal_type_name` est une **colonne réelle du dataset Kaggle**, pas une règle inventée — c'est le créateur du dataset qui a assigné le créneau de repas adapté pour chaque aliment.

#### Processus d'entraînement

```
1. Authentification backend NestJS (service account JWT)
2. Récupération catalogue complet GET /nutrition (pagination)
3. Filtrage : uniquement VALID_MEAL_TYPES = [Petit-déjeuner, Déjeuner, Dîner, Collation]
4. Feature engineering :
   └── 8 macros numériques
   └── One-hot encoding catégorie aliment (50+ catégories dynamiques)
5. Split stratifié 80/20
6. Balayage learning_rate [0.01, 0.05, 0.1, 0.2, 0.3] × CV 5-fold (F1 macro)
7. Entraînement final
8. Évaluation sur test set
9. Sauvegarde : meal_type_model.joblib + meal_type_categories.json
10. Rapport : docs/model-training-report-nutrition.md
```

#### Résultats réels (rapport du 2026-06-20)

**Balayage learning_rate (CV 5-fold, métrique F1 macro) :**

| learning_rate | F1 macro moyen | Écart-type |
|---|---|---|
| 0.01 | 0.3807 | 0.0319 |
| 0.05 | 0.4650 | 0.0331 |
| **0.1** | **0.4724** | 0.0267 |
| 0.2 | 0.4618 | 0.0504 |
| 0.3 | 0.4477 | 0.0395 |

**→ learning_rate retenu : 0.1** — doublement justifié : meilleur F1 moyen (0.4724) **et** écart-type le plus bas (0.0267), ce qui indique un modèle plus stable et moins sensible aux variations entre folds. Les scores sont cohérents (la courbe monte puis redescend logiquement), ce qui valide que le balayage a eu du sens. Un F1 macro de 0.47 sur 4 classes est honnête : les macros seules (calories, protéines, sucres...) ne déterminent pas univoquement le créneau de repas — un yaourt peut être petit-déjeuner ou collation, un œuf à n'importe quel repas. Le signal est faible par nature, et le modèle bat la baseline naïve de +21,6 points sans avoir gonflé le score artificiellement.

**Performance sur test set (hold-out 119 exemples) :**

| Métrique | Valeur |
|---|---|
| Exactitude (accuracy) | **0.5714** |
| Précision macro | **0.5222** |
| Rappel macro | **0.5113** |
| **F1-score macro** | **0.5068** |
| Baseline classe majoritaire (Dîner) | 0.3550 |
| **Gain vs baseline** | **+21.6 points** |

**Matrice de confusion (4 classes) :**

| Réel \ Prédit | Petit-déjeuner | Déjeuner | Dîner | Collation |
|---|---|---|---|---|
| **Petit-déjeuner** | 3 | 1 | 2 | 11 |
| **Déjeuner** | 2 | 13 | 12 | 0 |
| **Dîner** | 2 | 7 | 29 | 4 |
| **Collation** | 1 | 7 | 2 | 23 |

**Top features importantes :**

| Feature | Importance |
|---|---|
| `sugar_g` | 0.1915 |
| `sodium_mg` | 0.1398 |
| `calories` | 0.0791 |
| `protein_g` | 0.0751 |
| `carbs_g` | 0.0725 |
| `category_Repas/Transformé` | 0.0508 |
| `cholesterol_mg` | 0.0496 |

> **Note sur le F1 de 0.5068 :** c'est un score honnête et défendable. Les macros seules ne déterminent pas entièrement le créneau de repas (un yaourt peut se manger au petit-déjeuner ou en collation). Le modèle bat la baseline naïve de +21.6 points, ce qui démontre que le signal appris est réel.

---

## 6. Preuve d'entraînement pour le jury

### 6.1 Artefacts générés automatiquement

Tous les éléments suivants sont **générés automatiquement** par les scripts d'entraînement et versionnés dans le dépôt :

| Artefact | Chemin | Contenu |
|---|---|---|
| Modèle sport sérialisé | `app/contexts/workout/domain/data/exercise_scoring_model.joblib` | Les 100 arbres de décision avec tous leurs poids appris, convertis en fichier binaire via joblib. Permet de recharger le modèle instantanément au démarrage du serveur sans réentraîner (sinon ~34s à chaque démarrage). |
| Métriques sport | `app/contexts/workout/domain/data/exercise_scoring_model.joblib.metrics.json` | `{ "metric": 0.7958 }` — F1 du modèle actuellement déployé, utilisé par le ModelDeploymentGuard pour refuser tout réentraînement qui dégraderait les performances. |
| Modèle nutrition sérialisé | `app/contexts/nutrition/data/meal_type_model.joblib` | Même principe — MealTypeModel (4 classes) sérialisé via joblib. |
| Catégories nutrition | `app/contexts/nutrition/data/meal_type_categories.json` | Liste des classes connues |
| Rapport sport | `docs/model-training-report.md` | Données, CV, métriques, feature importance |
| Rapport nutrition | `docs/model-training-report-nutrition.md` | Données, CV, métriques, matrice confusion |

### 6.2 Comment reproduire l'entraînement devant le jury

```bash
# 1. Modèle sport
cd api-ia
python scripts/train_workout_model.py

# 2. Modèle nutrition (nécessite le backend NestJS en cours d'exécution)
python scripts/train_meal_type_model.py
```

Les deux scripts affichent en temps réel :
- Le nombre d'exemples chargés
- Les résultats de cross-validation pour chaque learning_rate
- Les métriques finales sur le test set (hold-out)
- La décision de déploiement (ModelDeploymentGuard)
- Et génèrent les rapports Markdown dans `docs/`

### 6.3 Garde-fou de déploiement (ModelDeploymentGuard)

Le système ne remplace jamais automatiquement un modèle par une version dégradée :

```python
# app/shared/domain/model_deployment_guard.py
def should_deploy(new_metric: float, previous_metric: float | None) -> bool:
    if previous_metric is None:
        return True   # Premier déploiement
    return new_metric >= previous_metric  # Déploie si égal ou meilleur
```

**Pourquoi c'est important pour la prod :** si le réentraînement hebdomadaire produit un modèle moins bon (données bruit, overfitting), l'ancien modèle reste actif sans aucune interruption de service.

### 6.4 Preuves supplémentaires disponibles

1. **Commits git** — les fichiers `.joblib` et rapports Markdown sont versionné avec les dates d'entraînement.
2. **Logs APScheduler** — le planificateur hebdomadaire trace chaque exécution (timestamp, résultat, décision déploiement).
3. **Collections MongoDB** — `workout_feedbacks` contient les 7 077 feedbacks réels qui ont alimenté l'entraînement.
4. **Rapport Markdown reproductible** — le fichier `docs/model-training-report.md` est régénéré à chaque entraînement avec la date exacte (`2026-06-20T20:58:19`).

---

## 7. Communication backend NestJS ↔ api-ia

### 7.1 Vue d'ensemble

Le backend NestJS est le **seul point d'entrée** pour le client (mobile/web). Il ne donne jamais accès direct à api-ia — il joue le rôle d'orchestrateur : il charge les données utilisateur depuis MariaDB, construit la requête pour api-ia, l'appelle, persiste le résultat, et retourne la réponse au client.

```
Client (JWT)
  │
  ▼
Backend NestJS
  │  1. Vérifie JWT
  │  2. Charge User + UserAiPreferences + HealthProfile (MariaDB)
  │  3. Construit le payload pour api-ia
  │  4. POST → api-ia (X-API-Key)
  │  5. Persiste résultat (MariaDB AiWorkoutRecommendation / AiNutritionRecommendation)
  │  6. Retourne réponse au client
  ▼
Client
```

**Variables d'environnement côté backend :**
```env
WORKOUT_SERVICE_URL=http://localhost:8000    # URL du micro-service api-ia
WORKOUT_SERVICE_API_KEY=change-me            # Doit correspondre à BACKEND_API_KEY dans api-ia
```

---

### 7.2 Flux — Génération de programme sportif

**Endpoint client :** `POST /ai/workout/generate` (JWT requis)

```
1. Backend charge depuis MariaDB :
   └── User.aiPreferences  → objectif_ia, contraintes_materielles, regime, allergies,
                              limitations_physiques, preferences_sportives
   └── User.healthProfile  → physical_activity_level

2. Mapping physical_activity_level → niveau api-ia :
   ┌─────────────────────────────────────┬───────────────┐
   │ sedentaire / debutant / faible      │ debutant      │
   │ modere / intermediaire / actif      │ intermediaire │
   │ eleve / avance                      │ avance        │
   │ athlete                             │ athlete       │
   └─────────────────────────────────────┴───────────────┘

3. WorkoutMicroserviceClient.generateProgram() →
   POST {WORKOUT_SERVICE_URL}/recommendations/workout
   Header : X-API-Key: {WORKOUT_SERVICE_API_KEY}
   Timeout : 10 secondes
   Body :
   {
     "userId": 42,
     "objectif": "renforcement",       ← aiPreferences.objectif_ia
     "niveau": "intermediaire",        ← mappé depuis healthProfile.physical_activity_level
     "materiel": ["haltères", "tapis"],← aiPreferences.contraintes_materielles
     "preferences": ["vegetarien"],    ← aiPreferences.regime (si défini)
     "limitations": ["arachide"]       ← aiPreferences.allergies
   }

4. api-ia répond → programme 7 jours avec programId (ObjectId MongoDB)

5. Backend archive l'ancienne recommandation ACTIVE de l'utilisateur :
   UPDATE AiWorkoutRecommendation SET statut='ARCHIVED' WHERE user_id=42 AND statut='ACTIVE'

6. Backend crée la nouvelle ligne :
   INSERT AiWorkoutRecommendation (user_id=42, microservice_ref_id=programId, statut='ACTIVE')
   → L'id MongoDB du programme est stocké en SQL comme clé logique (pas de FK réelle)

7. Réponse retournée au client : programme complet + recommendationId SQL
```

---

### 7.3 Flux — Génération de plan de repas

**Endpoint client :** `POST /ai/nutrition/meal-plan` (JWT requis)

```
1. Backend charge depuis MariaDB :
   └── User → date_of_birth, gender, height
   └── User.healthProfile → weight, physical_activity_level, daily_calories_target

2. Calcule l'âge depuis date_of_birth (en années, à la milliseconde près)

3. AiNutritionService →
   POST {WORKOUT_SERVICE_URL}/ai/nutrition/meal-plan
   Header : X-API-Key: {WORKOUT_SERVICE_API_KEY}
   Timeout : 15 secondes (plus long que le workout car LLM/MealComposer peut être lent)
   Body :
   {
     "userId": 42,
     "userGoal": "equilibre",                 ← hardcodé dans le service (oubli : aiPreferences.objectif_ia
                                                 n'est pas chargé dans AiNutritionService, contrairement
                                                 à AiWorkoutService qui charge bien les préférences IA)
     "weightKg": 72.5,                        ← healthProfile.weight
     "heightCm": 178.0,                       ← user.height
     "ageYears": 28,                          ← calculé depuis date_of_birth
     "gender": "male",                        ← user.gender
     "physicalActivityLevel": "moderately_active", ← healthProfile.physical_activity_level
     "dailyCaloriesTarget": 2200              ← healthProfile.daily_calories_target
   }

4. api-ia répond → plan 7 jours (MealComposer sur catalogue Kaggle en priorité)

5. Backend persiste le résultat :
   INSERT AiNutritionRecommendation (user_id=42, type='MEAL_PLAN', meal_plan={JSON complet})

6. Réponse retournée au client : plan 7 jours avec notes et modelStatus
```

---

### 7.4 Récupérer un programme existant

Le backend stocke uniquement le `microservice_ref_id` (ObjectId MongoDB) en SQL — pas le contenu du programme. Pour afficher le programme d'un utilisateur (ex. il revient le lendemain), le backend rappelle api-ia :

```
GET {WORKOUT_SERVICE_URL}/recommendations/workout/<microservice_ref_id>
Header : X-API-Key: {WORKOUT_SERVICE_API_KEY}

→ Retourne le WorkoutProgramResponse complet depuis MongoDB
→ 404 si l'ID est invalide ou le programme introuvable
```

Implémenté dans `app/routers/recommendations.py` (`GetWorkoutProgramUseCase` → `MongoWorkoutProgramRepository.find_raw_by_id()`).

---

### 7.5 Ce que le backend ne fait PAS encore

- Il **ne transmet pas** `limitations_physiques` ni `preferences_sportives` de `UserAiPreferences` au micro-service workout — seuls `objectif_ia`, `contraintes_materielles`, `regime` et `allergies` sont envoyés. Ticket : [#199](https://github.com/MSPR-c-l-w/backend/issues/199).
- `AiNutritionService` **n'utilise pas** `UserAiPreferences` — `objectif_ia` n'est pas transmis comme `userGoal`, hardcodé à `'equilibre'`. Ticket : [#198](https://github.com/MSPR-c-l-w/backend/issues/198).
- Il **ne valide pas** le contenu retourné par api-ia — comportement normal pour un service interne.

---

## 8. Infrastructure & persistence

### 7.1 MongoDB — Collections

| Collection | Description | Utilisée par |
|---|---|---|
| `workout_programs` | Programmes générés (7 jours, exercices scorés) | CreateWorkoutProgramUseCase |
| `workout_feedbacks` | Feedbacks utilisateurs (rating, problèmes, difficultés) | SubmitWorkoutFeedbackUseCase + entraînement ML |
| `user_fitness_profiles` | Profils évolutifs (niveau, limitations temporaires, historique) | SubmitWorkoutFeedbackUseCase |
| `nutrition_recommendations` | Plans de repas générés (7 jours) | GenerateMealPlanUseCase |
| `nutrition_foods` | Catalogue aliments Kaggle (600+ aliments) | AnalyzeMealUseCase, MealComposer |

### 7.2 Connexion Motor (async)

Motor est le driver MongoDB asynchrone. La connexion est gérée via le mécanisme **lifespan ASGI** de Flask/Hypercorn :

```
Démarrage app → startup ASGI → Motor client créé dans la boucle Hypercorn
  → Ping MongoDB (vérification)
  → Création indexes
  → get_database() disponible dans tous les use cases

Arrêt app → shutdown ASGI → Motor client fermé proprement
```

**Avantage :** le client Motor est créé dans la bonne boucle asyncio (celle de Hypercorn), évitant les problèmes de boucle fermée.

### 7.3 Indexes MongoDB

Indexes créés au démarrage (`app/shared/infrastructure/indexes.py`) :

- `workout_programs` : index sur `user_id`, `statut`, `generated_at`
- `workout_feedbacks` : index sur `user_id`, `program_id`, `created_at`
- `user_fitness_profiles` : index unique sur `user_id`
- `nutrition_recommendations` : index sur `user_id`, `created_at`
- `nutrition_foods` : index sur `name`, `category`

### 7.4 Cache applicatif (en mémoire)

| Cache | TTL | Clé | Contenu |
|---|---|---|---|
| Vision | 1 heure | URL de l'image | Liste `VisionDetection` |
| LLM suggestions | 24 heures | `goal + imbalance_tokens` | Suggestions texte |

---

## 8. Authentification & sécurité

### 8.1 API Key (header X-API-Key)

Le backend NestJS communique avec `api-ia` via une **clé API partagée** (variable `BACKEND_API_KEY`).

**Décorateur :** `@require_api_key` dans `app/dependencies/api_key.py`

**Routes protégées :**
- `POST /recommendations/workout` — génération programme
- `POST /recommendations/workout/<id>/feedback` — feedback
- `POST /ai/nutrition/analyze-photo` — analyse photo (flux backend → api-ia)

**Erreur si clé absente ou invalide :** HTTP 401 `{"error": "INVALID_API_KEY"}`

### 8.2 Routes publiques

- `GET /health` — health check
- `POST /ai/nutrition/analyze` — analyse directe (front ou tests)
- `POST /ai/nutrition/meal-plan` — plan de repas

### 8.3 Authentification service account (entraînement nutrition)

Le script `train_meal_type_model.py` s'authentifie au backend NestJS via `POST /auth/login` avec les credentials `BACKEND_SERVICE_EMAIL` + `BACKEND_SERVICE_PASSWORD` pour récupérer le catalogue nutrition.

---

## 9. Endpoints API

### GET /health

```http
GET /health
→ 200 OK
{
  "status": "ok",
  "timestamp": "2026-06-20T12:00:00Z"
}
```

---

### POST /ai/nutrition/analyze

Analyse d'un repas (photo ou base64).

**Requête :**
```json
{
  "imageUrl": "https://example.com/repas.jpg",
  "userGoal": "perte_de_poids",
  "weightKg": 75.0,
  "heightCm": 175.0,
  "ageYears": 30,
  "gender": "male",
  "physicalActivityLevel": "moderately_active"
}
```

**Réponse :**
```json
{
  "detectedFoods": [
    {"label": "poulet grillé", "confidence": 0.91},
    {"label": "riz basmati", "confidence": 0.88}
  ],
  "estimatedCalories": 520,
  "estimatedMacros": {
    "proteins_g": 32,
    "carbs_g": 54,
    "fats_g": 14,
    "fibers_g": 3.0
  },
  "imbalanceStatus": "EQUILIBRE",
  "nutrientDetails": [
    {"name": "proteins_g", "actual": 32.0, "target": 25.0, "unit": "g", "status": "OK", "deviation_pct": 28.0}
  ],
  "feedback": ["Repas bien équilibré pour votre objectif de perte de poids."],
  "modelStatus": "ollama_vision_active"
}
```

---

### POST /ai/nutrition/meal-plan

Génération d'un plan alimentaire 7 jours.

**Requête :**
```json
{
  "userId": 42,
  "userGoal": "equilibre",
  "dietaryConstraints": ["vegan"],
  "allergies": ["arachide"],
  "budget": 350.0
}
```

**Réponse :**
```json
{
  "userGoal": "equilibre",
  "days": [
    {
      "day": "lundi",
      "breakfast": "Porridge avoine + fruits rouges + graines de chia",
      "lunch": "Bowl de quinoa, pois chiches, légumes rôtis, sauce tahini",
      "dinner": "Curry de lentilles corail, riz complet, épinards",
      "snack": "Pomme + amandes",
      "estimatedCalories": 1920.0
    }
  ],
  "notes": ["Plan généré par le modèle de langage.", "Budget estimé : 340€/mois."],
  "modelStatus": "llm_active"
}
```

---

### POST /recommendations/workout

Génération d'un programme sportif (protégé X-API-Key).

**Requête :**
```json
{
  "userId": 42,
  "objectif": "renforcement",
  "niveau": "intermediaire",
  "materiel": ["haltères", "tapis"],
  "preferences": ["force", "polyarticulaire"],
  "limitations": ["genou"]
}
```

**Réponse :**
```json
{
  "programId": "507f1f77bcf86cd799439011",
  "userId": 42,
  "statut": "ACTIVE",
  "generatedAt": "2026-06-20T12:00:00Z",
  "programme": [
    {
      "jour": "lundi",
      "isRestDay": false,
      "estimatedSessionMinutes": 45,
      "exercices": [
        {"id": "curl-biceps", "name": "Curl biceps", "sets": 3, "reps": 12, "estimatedDurationMinutes": 8},
        {"id": "rowing-haltere", "name": "Rowing haltère", "sets": 3, "reps": 10, "estimatedDurationMinutes": 10}
      ]
    },
    {"jour": "mardi", "isRestDay": true, "estimatedSessionMinutes": 0, "exercices": []}
  ]
}
```

---

### POST /recommendations/workout/<id>/feedback

**Requête :**
```json
{
  "rating": 4,
  "tropDifficile": false,
  "tropFacile": false,
  "exercicesProblematiques": ["curl-biceps"]
}
```

**Réponse :**
```json
{
  "feedbackId": "507f1f77bcf86cd799439012",
  "programId": "507f1f77bcf86cd799439011",
  "userId": 42,
  "profileNiveau": "intermediaire",
  "createdAt": "2026-06-20T12:01:00Z"
}
```

---

## 10. Gestion des erreurs

### Exceptions applicatives

| Exception | Code HTTP | Code erreur JSON |
|---|---|---|
| `InsufficientUserDataError` | 400 | `INSUFFICIENT_USER_DATA` |
| `ProgramNotFoundError` | 404 | `PROGRAM_NOT_FOUND` |
| `MongoUnavailableError` | 503 | `MONGODB_UNAVAILABLE` |
| Erreur de validation Pydantic | 422 | `VALIDATION_ERROR` |
| Clé API invalide | 401 | `INVALID_API_KEY` |

### Format des erreurs

```json
{
  "error": "PROGRAM_NOT_FOUND",
  "detail": "Programme 507f1f77bcf86cd799439011 introuvable."
}
```

---

## 11. Réentraînement automatique

### Planning

| Modèle | Jour | Heure UTC | Script |
|---|---|---|---|
| ExerciseScoringModel (sport) | Dimanche | 03:00 | `scripts/train_workout_model.py` |
| MealTypeModel (nutrition) | Dimanche | 04:00 | `scripts/train_meal_type_model.py` |

### Processus

```
APScheduler déclenche le job
  │
  ▼
Sous-processus Python isolé (sys.executable)
  │  Évite les conflits de boucle asyncio
  ▼
Chargement données (MongoDB + catalogue backend NestJS)
  │
  ▼
Entraînement (CV + entraînement final)
  │
  ▼
ModelDeploymentGuard.should_deploy(new_f1, old_f1)
  │
  ├── Si True → sauvegarde .joblib + .metrics.json + rapport Markdown
  └── Si False → logs d'alerte, ancien modèle conservé (0 downtime)
```

### Activation

Le planificateur est désactivé par défaut (`ENABLE_RETRAINING_SCHEDULER=false`). Il ne fonctionne que si le serveur api-ia tourne au moment du déclenchement — c'est un scheduler in-process (APScheduler dans Hypercorn), pas un cron système. Les jobs manqués (serveur éteint) ne sont pas rattrapés au redémarrage. Pour un environnement de production critique, il faudrait un cron système externe (`crontab`) ou un orchestrateur (Kubernetes CronJob) qui lance le script indépendamment du serveur.

---

## 12. Tests

### Couverture

- **329 tests** au total (310 unitaires + 19 intégration/e2e)
- **93,7% de couverture** (2 488 instructions analysées, 157 non couvertes)
- Couverture minimum exigée : 40% (dépassée de +53 points)

### Marqueurs

```python
@pytest.mark.unit         # Aucun service externe requis
@pytest.mark.integration  # MongoDB requis
@pytest.mark.e2e          # Stack complète requise
```

### Commandes

```bash
# Tests unitaires uniquement (recommandé en CI)
pytest -m "not integration and not e2e"

# Avec couverture
pytest -m "not integration and not e2e" --cov=app --cov-report=term-missing

# Tous les tests
pytest
```

### Modules couverts à 100%

`exercises_catalog.py`, `api_key.py`, `schemas.py`, `recommendation_engine.py`,
`weekly_planner.py`, `exception_handlers.py`, `http.py`, `health.py`, `nutrition.py`,
`recommendations.py`, `routers/__init__.py`, `model_deployment_guard.py`

---

## 13. Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017/healthai_coach` | URI MongoDB |
| `BACKEND_API_KEY` | — | Clé partagée backend ↔ api-ia |
| `BACKEND_URL` | `http://localhost:3001` | URL du backend NestJS |
| `BACKEND_SERVICE_EMAIL` | — | Email service account (entraînement nutrition) |
| `BACKEND_SERVICE_PASSWORD` | — | Mot de passe service account |
| `NUTRITION_VISION_OLLAMA_ENDPOINT` | — | Endpoint Ollama vision (ex: `http://localhost:11434`) |
| `NUTRITION_VISION_OLLAMA_MODEL` | `llava` | Modèle vision Ollama |
| `NUTRITION_GOOGLE_VISION_ENDPOINT` | — | Endpoint Google Vision API |
| `NUTRITION_GOOGLE_VISION_API_KEY` | — | Clé Google Vision |
| `NUTRITION_LLM_ENDPOINT` | — | Endpoint Ollama NLP |
| `ENABLE_RETRAINING_SCHEDULER` | `false` | Active le planificateur hebdomadaire |
| `PORT` | `8000` | Port d'écoute |
| `ENVIRONMENT` | `development` | Environnement |

---

## 14. Chiffres clés

| Élément | Valeur |
|---|---|
| Tests automatisés | 329 (dont 310 unitaires) |
| Couverture de code | 93,7% |
| Exercices dans le catalogue | Catalogue backend NestJS (table `Exercise`, ETL GitHub JSON) — nombre dépendant des données importées. Fallback statique : 80+ exercices. |
| Features modèle sport | 7 features numériques |
| Données d'entraînement sport | 8 877 exemples (7 077 réels + 1 800 synthétiques) |
| F1-score modèle sport | **0.7958** |
| Aliments catalogue Kaggle | 600+ |
| Données d'entraînement nutrition | 595 aliments réels |
| F1-score macro modèle nutrition | **0.5068** (+21,6 pts vs baseline) |
| Fenêtre rotation exercices | 2 semaines |
| Durée limitation temporaire | 30 jours |
| Seuil confiance vision IA | 0.5 |
| Tolérance déséquilibre nutritionnel | ±15% |
| Seuil label "satisfait" (sport) | rating ≥ 4 / 5 |
| Cache vision | 1 heure |
| Cache LLM | 24 heures |
| Réentraînement automatique | Chaque dimanche (03h sport, 04h nutrition) |
