# Guide d'utilisation — HealthAI Coach API

## Prérequis

- Python 3.12+
- Docker & Docker Compose (recommandé)
- Un backend NestJS accessible (pour les endpoints de recommandations sport)

---

## Installation

```bash
# Cloner le projet et se placer dedans
python3 -m venv .venv
source .venv/bin/activate        # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

---

## Configuration

Copier le fichier d'exemple et adapter les valeurs :

```bash
cp .env.example .env
```

| Variable | Description | Défaut |
|---|---|---|
| `SECRET_KEY` | Clé secrète Flask | `dev-secret-key` |
| `ENVIRONMENT` | `development` ou `offline` | `development` |
| `MONGODB_URI` | URI MongoDB | `mongodb://localhost:27017/healthai_coach` |
| `BACKEND_URL` | URL du backend NestJS | `http://localhost:3001` |
| `BACKEND_TIMEOUT` | Timeout appels backend (s) | `10` |
| `HUGGINGFACE_API_KEY` | Token HuggingFace (vision + LLM) | *(optionnel)* |
| `GOOGLE_APPLICATION_CREDENTIALS` | Chemin vers le fichier JSON Google Vision | *(optionnel)* |
| `NUTRITION_LLM_ENDPOINT` | Endpoint Ollama ou autre LLM | *(optionnel)* |
| `NUTRITION_LLM_API_KEY` | Clé API LLM | *(optionnel)* |
| `NUTRITION_LLM_TIMEOUT_SECONDS` | Timeout LLM (s) | `10` |

> Sans variables vision/LLM, l'API fonctionne entièrement en **mode fallback statique** — adapté au développement et aux tests.

> En mode `ENVIRONMENT=offline`, l'endpoint de recommandations sport retourne une réponse vide sans appeler le backend.

---

## Lancement

### Avec Docker (recommandé)

```bash
docker compose up --build -d
```

L'API écoute sur `http://localhost:8000`, MongoDB sur le port `27017`.

### En local

```bash
python3 run.py
```

L'API écoute sur `http://127.0.0.1:8000`.

---

## Endpoints

### `GET /health`

Vérifie que l'API est en ligne.

```bash
curl http://localhost:8000/health
```

```json
{ "status": "ok", "service": "healthai-coach-api", "version": "0.1.0" }
```

---

### `POST /ai/nutrition/analyze`

Analyse une photo de repas et retourne macros, déséquilibres nutritionnels et conseils personnalisés selon le profil biométrique de l'utilisateur.

**Body JSON** :

```json
{
  "imageUrl": "https://exemple.com/repas.jpg",
  "userGoal": "perte_de_poids",
  "weightKg": 75.0,
  "heightCm": 175.0,
  "ageYears": 30,
  "gender": "male",
  "physicalActivityLevel": "moderately_active"
}
```

| Champ | Type | Requis | Description |
|-------|------|--------|-------------|
| `imageUrl` | `string` | Oui* | URL publique de la photo |
| `imageBase64` | `string` | Oui* | Alternative : image en base64 |
| `userGoal` | `string` | Non | `perte_de_poids` \| `prise_de_masse` \| `equilibre` |
| `weightKg` | `float` | Non | Poids kg — `HealthProfile.weight` du backend |
| `heightCm` | `float` | Non | Taille cm — `User.height` du backend |
| `ageYears` | `integer` | Non | Âge — calculé depuis `User.date_of_birth` |
| `gender` | `string` | Non | `male` \| `female` — `User.gender` |
| `physicalActivityLevel` | `string` | Non | `sedentary` \| `lightly_active` \| `moderately_active` \| `very_active` \| `extra_active` |
| `dailyCaloriesTarget` | `integer` | Non | Override TDEE — `HealthProfile.daily_calories_target` |

*\* `imageUrl` ou `imageBase64` obligatoire.*

**Réponse** :

```json
{
  "detectedFoods": [{ "label": "poulet", "confidence": 0.91 }],
  "estimatedCalories": 520,
  "estimatedMacros": { "proteins_g": 32, "carbs_g": 54, "fats_g": 14, "fibers_g": 3.0 },
  "imbalanceStatus": "EQUILIBRE",
  "nutrientDetails": [
    { "name": "calories", "actual": 520, "target": 566.7, "unit": "kcal", "status": "OK", "deviation_pct": -8.2 }
  ],
  "feedback": ["Repas équilibré pour votre objectif."],
  "modelStatus": "stub_ready_for_huggingface"
}
```

> **Personnalisation biométrique** : si `weightKg`, `heightCm`, `ageYears` et `gender` sont fournis, les cibles sont calculées via la formule **Mifflin-St Jeor** (TDEE) au lieu des profils génériques. Voir `docs/nutrition-engine.md` pour le détail.

---

### `POST /ai/nutrition/meal-plan`

Génère un plan repas hebdomadaire (7 jours) adapté au profil utilisateur.

```bash
curl -X POST http://localhost:8000/ai/nutrition/meal-plan \
  -H "Content-Type: application/json" \
  -d '{
    "userGoal": "perte_de_poids",
    "dietaryConstraints": ["vegetarien"],
    "allergies": ["arachide"],
    "weightKg": 60,
    "heightCm": 163,
    "ageYears": 28,
    "gender": "female",
    "physicalActivityLevel": "sedentary"
  }'
```

**Réponse** :

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
  "notes": ["Plan généré en mode stub local."],
  "modelStatus": "stub_ready_for_llm"
}
```

---

### `POST /api/nutrition/analyze` *(legacy)*

Alias de compatibilité vers `/ai/nutrition/analyze`. Même contrat.

---

### `POST /api/recommendations/predict`

Recommande des repas personnalisés selon les biométriques de l'utilisateur.

**Authentification requise** : Bearer JWT (même token que le backend).

```json
{
  "meal_type": "lunch",
  "dietary_constraints": ["low_sodium"],
  "top_n": 5
}
```

| Champ | Valeurs possibles | Défaut |
|---|---|---|
| `meal_type` | `breakfast`, `lunch`, `dinner`, `snack` | `lunch` |
| `dietary_constraints` | `low_carb`, `high_protein`, `low_fat`, `low_sodium`, `low_sugar`, `vegetarian`, `vegan` | `[]` |
| `top_n` | 1 – 20 | `5` |

---

### `POST /api/recommendations/train`

Ré-entraîne le modèle Random Forest et le recharge en mémoire.

```bash
curl -X POST http://localhost:8000/api/recommendations/train
```

---

## Documentation interactive (Swagger)

| URL | Description |
|---|---|
| `http://localhost:8000/docs/swagger` | Interface Swagger UI |
| `http://localhost:8000/docs/openapi.json` | Spec OpenAPI JSON |

---

## Tests

```bash
# Tous les tests
python3 -m pytest tests/

# Tests nutritionnels uniquement
python3 -m pytest tests/test_nutrition*.py -v
```

---

## Documentation complémentaire

| Fichier | Description |
|---------|-------------|
| `docs/nutrition-engine.md` | Documentation complète du moteur nutritionnel (EPIC #78) — TDEE, flux, composants, intégration backend |
| `docs/architecture.md` | Architecture clean (bounded contexts, ports & adapters) |
| `docs/mongodb-schema.md` | Schéma MongoDB (moteur sport) |
| `openapi.json` | Spec OpenAPI générée — régénérer avec `python3 scripts/export_openapi.py` |
