# Moteur de recommandations nutritionnelles — EPIC #78

> Documentation technique complète du contexte `nutrition` — HealthAI Coach API-IA.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Endpoints HTTP](#3-endpoints-http)
4. [Flux de traitement détaillé](#4-flux-de-traitement-détaillé)
5. [Personnalisation biométrique (TDEE)](#5-personnalisation-biométrique-tdee)
6. [Composants clés](#6-composants-clés)
7. [Intégration avec le backend](#7-intégration-avec-le-backend)
8. [Gestion du cache](#8-gestion-du-cache)
9. [Tests](#9-tests)
10. [Variables d'environnement](#10-variables-denvironnement)
11. [Tickets couverts](#11-tickets-couverts)

---

## 1. Vue d'ensemble

Le moteur nutritionnel analyse des photos de repas et génère des plans alimentaires **personnalisés** selon le profil biométrique de l'utilisateur.

```
Photo de repas ──► Détection aliments ──► Calcul macros ──► Analyse déséquilibre ──► Conseils IA
                       (Vision IA)          (table interne)     (TDEE ou objectif)       (LLM)
```

**Fonctionnalités principales :**
- Détection des aliments via Google Vision
  - Estimation des macronutriments (protéines, glucides, lipides, fibres, calories)
- Calcul des besoins caloriques **personnalisé** par biométrie (formule Mifflin-St Jeor)
- Détection des déséquilibres nutritionnels (±15 % de tolérance)
- Génération de conseils textuels (LLM Ollama ou fallback FR statique)
- Plan repas hebdomadaire sur 7 jours
- Cache in-memory TTL pour éviter les appels redondants

---

## 2. Architecture

Le contexte suit la **clean architecture** par bounded context :

```
app/contexts/nutrition/
├── domain/
│   ├── models.py          # Entités : Macros, HealthProfile, NutrientDetail, enums
│   ├── services.py        # NutritionImbalanceService (détection déséquilibres)
│   └── tdee.py            # TdeeCalculator (BMR + PAL → cibles personnalisées)
├── application/
│   └── use_cases/
│       ├── analyze_meal.py       # AnalyzeMealUseCase — pipeline complet analyse repas
│       └── generate_meal_plan.py # GenerateMealPlanUseCase — génération plan 7 jours
├── infrastructure/
│   ├── vision/
│   │   └── google_vision_provider.py # Google Vision
│   ├── nutrition_lookup.py  # Table de référence nutritionnelle (40 aliments)
│   ├── llm_provider.py      # LLM Ollama + fallback statique FR
│   └── cache.py             # AiCacheService (TTL, SHA-256 keys)
└── presentation/
    └── schemas.py           # DTOs Pydantic : Request/Response
```

**Règles d'architecture :**
- Le domaine (`domain/`) n'importe rien de Flask, Motor, ni d'aucune infrastructure.
- Les use cases (`application/`) lèvent `ApplicationError`, jamais de `HTTPException`.
- Le câblage se fait exclusivement dans `app/composition/container.py`.

---

## 3. Endpoints HTTP

### `POST /ai/nutrition/analyze`

Analyse une photo de repas et retourne macros, déséquilibres et conseils personnalisés.

**Request body :**

```json
{
  "imageUrl": "https://example.com/meal.jpg",
  "imageBase64": null,
  "userGoal": "perte_de_poids",

  // Champs biométriques (transmis par le backend depuis User + HealthProfile)
  "weightKg": 75.0,
  "heightCm": 175.0,
  "ageYears": 30,
  "gender": "male",
  "physicalActivityLevel": "moderately_active",
  "dailyCaloriesTarget": null
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `imageUrl` | `string (url)` | Oui* | URL publique de la photo |
| `imageBase64` | `string` | Oui* | Alternatively, image encodée en base64 |
| `userGoal` | `string` | Non | `perte_de_poids` \| `prise_de_masse` \| `equilibre` |
| `weightKg` | `float` | Non | Poids en kg (`HealthProfile.weight`) |
| `heightCm` | `float` | Non | Taille en cm (`User.height`) |
| `ageYears` | `integer` | Non | Âge calculé depuis `User.date_of_birth` |
| `gender` | `string` | Non | `male` \| `female` (`User.gender`) |
| `physicalActivityLevel` | `string` | Non | Voir [niveaux d'activité](#niveaux-dactivité) |
| `dailyCaloriesTarget` | `integer` | Non | Override TDEE si fourni (`HealthProfile.daily_calories_target`) |

*\* `imageUrl` ou `imageBase64` obligatoire.*

**Response body (200) :**

```json
{
  "detectedFoods": [
    { "label": "poulet", "confidence": 0.91 },
    { "label": "brocoli", "confidence": 0.87 }
  ],
  "estimatedCalories": 520,
  "estimatedMacros": {
    "proteins_g": 32.0,
    "carbs_g": 54.0,
    "fats_g": 14.0,
    "fibers_g": 3.0
  },
  "imbalanceStatus": "EQUILIBRE",
  "nutrientDetails": [
    {
      "name": "calories",
      "actual": 520.0,
      "target": 566.7,
      "unit": "kcal",
      "status": "OK",
      "deviation_pct": -8.2
    },
    {
      "name": "proteins_g",
      "actual": 32.0,
      "target": 30.0,
      "unit": "g",
      "status": "OK",
      "deviation_pct": 6.7
    }
  ],
  "feedback": [
    "Augmentez légèrement les portions ou ajoutez une collation nutritive."
  ],
  "modelStatus": "vision_stub"
}
```

---

### `POST /ai/nutrition/meal-plan`

Génère un plan repas hebdomadaire (7 jours) adapté au profil utilisateur.

**Request body :**

```json
{
  "userGoal": "perte_de_poids",
  "dietaryConstraints": ["vegetarien"],
  "allergies": ["arachide"],
  "weightKg": 60.0,
  "heightCm": 163.0,
  "ageYears": 28,
  "gender": "female",
  "physicalActivityLevel": "sedentary",
  "dailyCaloriesTarget": null
}
```

**Response body (200) :**

```json
{
  "userGoal": "perte_de_poids",
  "days": [
    {
      "day": 1,
      "breakfast": "Skyr + fruits rouges + flocons d'avoine",
      "lunch": "Salade quinoa, pois chiches, légumes croquants",
      "dinner": "Saumon, brocoli vapeur, patate douce",
      "snack": "Une pomme",
      "estimatedCalories": 1200
    }
  ],
  "notes": [
    "Plan généré en mode stub local.",
    "Exclut les allergènes déclarés."
  ],
  "modelStatus": "stub_ready_for_llm"
}
```

---

### `POST /api/nutrition/analyze` *(legacy)*

Alias de compatibilité vers `/ai/nutrition/analyze`. Même contrat, même réponse.

---

### Codes d'erreur

| Code | Signification |
|------|---------------|
| `400` | Payload invalide (champ manquant, type incorrect) |
| `413` | Image trop volumineuse |
| `503` | Tous les providers IA sont indisponibles |

---

## 4. Flux de traitement détaillé

### `AnalyzeMealUseCase`

```
┌─────────────────────────────────────────────────────────────┐
│  1. Cache check (vision)                                    │
│     SHA-256(imageUrl | imageBase64_len) → TTL 1h            │
│                                                             │
│  2. Vision detection                                        │
│     Google Vision                                           │
│     ┌─ Confidence filter : score ≥ 0.5                      │
│     └─ Non-food filter   : labels génériques exclus         │
│                                                             │
│  3. Calcul macros (NutritionLookupService)                  │
│     Lookup table 40 aliments + portion 150g/aliment         │
│     Si absent → estimation par défaut (flagged estimated)   │
│                                                             │
│  4. Résolution profil de santé                              │
│     a. dailyCaloriesTarget fourni → profil direct           │
│     b. Biométrie complète → TdeeCalculator.compute()        │
│     c. Fallback → GOAL_PROFILES[userGoal]                   │
│                                                             │
│  5. Détection déséquilibres (NutritionImbalanceService)     │
│     Cible repas = profil_journalier / 3                     │
│     Tolérance ±15% → OK | EXCES | DEFICIT                   │
│     MealStatus = EQUILIBRE si tous OK, sinon DESEQUILIBRE   │
│                                                             │
│  6. Génération conseils LLM                                 │
│     Cache check (LLM) → TTL 24h                             │
│     LlmProvider (Ollama → fallback statique)                │
│                                                             │
│  7. Réponse assemblée                                       │
└─────────────────────────────────────────────────────────────┘
```

### `GenerateMealPlanUseCase`

```
┌──────────────────────────────────────────────────┐
│  1. Résolution calories journalières             │
│     a. dailyCaloriesTarget fourni → direct       │
│     b. Biométrie complète → TDEE                 │
│     c. Fallback → GOAL_PROFILES[goal].calories   │
│                                                  │
│  2. Génération plan 7 jours                      │
│     LlmProvider → stub statique FR si echec      │
│     Filtrage allergènes + contraintes déclarées  │
│                                                  │
│  3. Injection calories personnalisées            │
│     estimatedCalories = calories calculées       │
└──────────────────────────────────────────────────┘
```

---

## 5. Personnalisation biométrique (TDEE)

### Formule utilisée : Mifflin-St Jeor

```
Homme :  BMR = 10 × poids(kg) + 6.25 × taille(cm) − 5 × âge(ans) + 5
Femme :  BMR = 10 × poids(kg) + 6.25 × taille(cm) − 5 × âge(ans) − 161

TDEE = BMR × coefficient_activité
```

### Niveaux d'activité

| `physicalActivityLevel` | Coefficient PAL | Description |
|------------------------|-----------------|-------------|
| `sedentary` | 1.20 | Travail de bureau, pas d'exercice |
| `lightly_active` | 1.375 | Exercice léger 1–3 jours/semaine |
| `moderately_active` | 1.55 | Exercice modéré 3–5 jours/semaine |
| `very_active` | 1.725 | Exercice intense 6–7 jours/semaine |
| `extra_active` | 1.90 | Métier physique + entraînement intense |

Valeur inconnue → fallback sur `moderately_active` (1.55).

### Ajustements par objectif

| `userGoal` | Ajustement | Protéines |
|------------|------------|-----------|
| `perte_de_poids` | −400 kcal | 1.8 g/kg |
| `equilibre` | ±0 kcal | 1.4 g/kg |
| `prise_de_masse` | +350 kcal | 2.2 g/kg |

**Plancher minimal** : 1 200 kcal/jour (aucune cible ne peut descendre en dessous).

### Exemple concret

```
Utilisateur : femme, 60 kg, 163 cm, 28 ans, sédentaire, objectif perte de poids

BMR  = 10×60 + 6.25×163 − 5×28 − 161
     = 600 + 1018.75 − 140 − 161 = 1317.75 kcal
TDEE = 1317.75 × 1.20 = 1581.3 kcal
Ajustement perte = −400 kcal → 1181.3 kcal → plancher → 1200 kcal/jour

Protéines = 1.8 × 60 = 108 g/jour
Repas     = 1200/3 = 400 kcal cible par repas
```

### Priorité de résolution

```
1. dailyCaloriesTarget fourni explicitement  ← priorité absolue
2. Biométrie complète (poids + taille + âge + genre) → TDEE
3. GOAL_PROFILES[userGoal] (profils statiques génériques)
```

---

## 6. Composants clés

### `TdeeCalculator` (`domain/tdee.py`)

```python
from app.contexts.nutrition.domain.tdee import TdeeCalculator

calc = TdeeCalculator()
profile = calc.compute(
    weight_kg=75,
    height_cm=175,
    age_years=30,
    gender="male",
    physical_activity_level="moderately_active",
    goal="perte_de_poids",
)
# profile.daily_calories_target → int (kcal/jour)
# profile.proteins_target_g     → float (g/jour)
# profile.carbs_target_g        → float (g/jour)
# profile.fats_target_g         → float (g/jour)
# profile.fibers_target_g       → float (g/jour)
```

---

### `NutritionImbalanceService` (`domain/services.py`)

Compare les macros d'un repas (1/3 de la cible journalière) :

```python
service = NutritionImbalanceService()
details, status = service.detect_imbalances(
    macros=macros,            # Macros mesurées
    health_profile=profile,  # HealthProfile TDEE (ou None → GOAL_PROFILES)
    goal="perte_de_poids",
)
# details : list[NutrientDetail]  — calories, proteins_g, carbs_g, fats_g, fibers_g
# status  : MealStatus.EQUILIBRE | MealStatus.DESEQUILIBRE
```

**Tolérance ±15 %** : un écart ≤15 % par rapport à la cible est classé `OK`.

---

### `NutritionLookupService` (`infrastructure/nutrition_lookup.py`)

Table de référence de **40 aliments** courants (valeurs pour 100 g) :

```python
lookup = NutritionLookupService()
macros = lookup.compute_macros(["poulet", "brocoli"])
# Portion par défaut : 150 g/aliment détecté
```

Aliments couverts (exemples) : poulet, riz, saumon, boeuf, tofu, oeuf, lentilles,
quinoa, pâtes, pain, brocoli, carotte, salade, pomme, banane, avocat, fromage, yaourt…

Si un aliment n'est pas dans la table → valeurs estimées par défaut, `macros.estimated = True`.

---

### `LlmProvider` (`infrastructure/llm_provider.py`)

Cascade de providers pour la génération de conseils :

```
1. Ollama (endpoint local configurable)
2. Fallback statique FR (messages prédéfinis par objectif + type de déséquilibre)
```

Le fallback statique garantit qu'un conseil pertinent est toujours retourné même sans accès LLM.

---

### `AiCacheService` (`infrastructure/cache.py`)

Cache in-memory avec TTL par entrée :

| Type | TTL par défaut | Clé |
|------|---------------|-----|
| Vision (détection aliments) | 1 h (3 600 s) | SHA-256(url ou taille base64) |
| LLM (conseils textuels) | 24 h (86 400 s) | SHA-256(goal + imbalances) |

```python
cache = AiCacheService()
key = cache.image_key(image_url, image_base64)
result = cache.get(key)            # None si absent ou expiré
cache.set(key, result, ttl_seconds=3600)
print(cache.stats)                 # {"hits": N, "misses": M}
```

---

## 7. Intégration avec le backend

L'API-IA **ne lit pas** la base de données backend. C'est le backend qui transmet
les données biométriques de l'utilisateur connecté dans chaque requête.

### Mapping Prisma → champs API-IA

```
Backend Prisma DB                   API-IA Request field
──────────────────────────────────────────────────────
User.height           (cm)    →     heightCm
User.date_of_birth    (date)  →     ageYears  (calculé: today - dob)
User.gender           (str)   →     gender
HealthProfile.weight  (kg)    →     weightKg
HealthProfile.physical_activity_level  →  physicalActivityLevel
HealthProfile.daily_calories_target    →  dailyCaloriesTarget
```

### Exemple d'appel depuis le backend (TypeScript)

```typescript
const user = await prisma.user.findUnique({ where: { id: userId } });
const health = await prisma.healthProfile.findUnique({ where: { userId } });

const ageYears = differenceInYears(new Date(), new Date(user.date_of_birth));

const response = await fetch(`${process.env.AI_API_URL}/ai/nutrition/analyze`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    imageUrl: req.body.imageUrl,
    userGoal: health.goal ?? "equilibre",
    weightKg: health.weight,
    heightCm: user.height,
    ageYears,
    gender: user.gender,
    physicalActivityLevel: health.physical_activity_level,
    dailyCaloriesTarget: health.daily_calories_target ?? null,
  }),
});
```

---

## 8. Gestion du cache

Le cache évite les appels redondants aux services externes :

```
Requête analyze ──► image_key ──► cache HIT  → retourne résultat stocké
                              └─► cache MISS → appel provider → stocke résultat
```

**Politique d'éviction** : lazy expiration — l'entrée est supprimée lors du prochain `get` si expirée.

Le cache est partagé pour toute la durée de vie du process (in-memory). En production multi-instance, remplacer par Redis.

---

## 9. Tests

```bash
# Tous les tests nutritionnels
python3 -m pytest tests/test_nutrition*.py -v

# Par module
python3 -m pytest tests/test_nutrition_domain.py   # Domaine (imbalance, modèles)
python3 -m pytest tests/test_nutrition_cache.py    # Cache + lookup + filtre confiance
python3 -m pytest tests/test_nutrition_fallback.py # Fallbacks et cas dégradés
python3 -m pytest tests/test_nutrition_tdee.py     # TDEE + biométrie intégration
python3 -m pytest tests/test_nutrition.py          # Endpoints HTTP (httpx)
```

**Couverture (38 tests) :**

| Fichier de test | Tests | Contenu |
|----------------|-------|---------|
| `test_nutrition_domain.py` | 6 | Imbalance service, modèles domaine |
| `test_nutrition_cache.py` | 15 | Cache TTL, lookup table, filtre confiance |
| `test_nutrition_fallback.py` | 5 | Fallback LLM, déséquilibres, feedback |
| `test_nutrition_tdee.py` | 10 | TdeeCalculator, intégration biométrique |
| `test_nutrition.py` | 2 | Endpoints HTTP `/ai/nutrition/analyze` et `/meal-plan` |

---

## 10. Variables d'environnement

```bash
# LLM (optionnel — fallback statique si absent)
NUTRITION_LLM_ENDPOINT=http://localhost:11434/api/generate   # Ollama
NUTRITION_LLM_API_KEY=
NUTRITION_LLM_TIMEOUT_SECONDS=10

# Vision providers (optionnel — filtre confiance ≥ 0.5)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account.json
```

Sans ces variables, le service fonctionne entièrement en mode **fallback statique** — adapté au développement et aux tests.

---

## 11. Tickets couverts

| Ticket | Description | Statut |
|--------|-------------|--------|
| #83 | Provider HuggingFace (food-detection) — supprimé | ~~✅~~ |
| #84 | Provider Google Vision (fallback) | ✅ |
| #85 | Filtre de confiance (seuil 0.5) + labels non-alimentaires | ✅ |
| #86 | `NutritionLookupService` — table de référence 40 aliments | ✅ |
| #87 | Endpoints `/ai/nutrition/analyze` et `/ai/nutrition/meal-plan` | ✅ |
| #88 | `NutritionImbalanceService` — détection déséquilibres ±15 % | ✅ |
| #89 | `LlmProvider` — conseils IA avec fallback statique FR | ✅ |
| #90 | `GenerateMealPlanUseCase` — plan 7 jours + LLM | ✅ |
| #91 | `AiCacheService` — cache in-memory TTL | ✅ |
| #92 | Documentation OpenAPI mise à jour | ✅ |
| TDEE | Personnalisation biométrique via Mifflin-St Jeor | ✅ |
