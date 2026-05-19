# Guide d'utilisation — HealthAI Coach API

## Prérequis

- Python 3.10+
- Un backend NestJS accessible (pour les endpoints de recommandations)

---

## Installation

```bash
# Cloner le projet et se placer dedans
python -m venv .venv
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

> En mode `ENVIRONMENT=offline`, l'endpoint de recommandations retourne une réponse vide sans appeler le backend.

---

## Lancement

```bash
python run.py
```

L'API écoute sur `http://127.0.0.1:5000`.

---

## Endpoints

### `GET /api/health/`

Vérifie que l'API est en ligne.

```bash
curl http://127.0.0.1:5000/api/health/
```

```json
{ "status": "ok", "service": "healthai-coach-api", "version": "0.1.0" }
```

---

### `POST /api/nutrition/analyze`

Analyse nutritionnelle d'un repas (stub prêt pour Hugging Face).

**Body JSON** :

```json
{
  "image_url": "https://exemple.com/repas.jpg",
  "image_base64": null,
  "user_goal": "prise de masse"
}
```

> `image_url` ou `image_base64` — les deux sont optionnels à ce stade.

**Réponse** :

```json
{
  "detected_foods": [{ "label": "poulet-riz", "confidence": 0.84 }],
  "estimated_calories": 520,
  "estimated_macros": { "proteins_g": 32, "carbs_g": 54, "fats_g": 14 },
  "feedback": ["Repas compatible avec un objectif de prise de masse.", "..."],
  "model_status": "stub_ready_for_huggingface"
}
```

---

### `POST /api/recommendations/predict`

Recommande des repas personnalisés selon les biométriques de l'utilisateur.

**Authentification requise** : Bearer JWT (même token que le backend).

**Body JSON** :

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

```bash
curl -X POST http://127.0.0.1:5000/api/recommendations/predict \
  -H "Authorization: Bearer <votre_token>" \
  -H "Content-Type: application/json" \
  -d '{"meal_type": "lunch", "top_n": 3}'
```

---

### `POST /api/recommendations/train`

Ré-entraîne le modèle Random Forest et le recharge en mémoire.

```bash
curl -X POST http://127.0.0.1:5000/api/recommendations/train
```

---

## Documentation interactive (Swagger)

| URL | Description |
|---|---|
| `http://127.0.0.1:5000/docs/swagger` | Interface Swagger UI |
| `http://127.0.0.1:5000/docs/openapi.json` | Spec OpenAPI JSON |

---

## Tests

```bash
pytest tests/
```
