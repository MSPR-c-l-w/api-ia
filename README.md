# HealthAI Coach API (api-ia)

Micro-service **FastAPI** + **MongoDB** (Motor) pour l'analyse nutritionnelle et les recommandations sportives IA.

Partie de l'[EPIC #79](https://github.com/MSPR-c-l-w/backend/issues/79) (issues suivies sur le dépôt `backend`).

## Structure

```text
app/
  main.py
  config.py
  routers/
    health.py
    nutrition.py
    recommendations.py
  models/
    schemas.py
  services/
    database.py
tests/
run.py
docker-compose.yml
Dockerfile
```

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | URI MongoDB (ex. `mongodb://localhost:27017/healthai_coach`) |
| `BACKEND_API_KEY` | Clé partagée avec le backend NestJS (auth inter-services, #99) |
| `PORT` | Port HTTP (défaut `8000`) |
| `ENVIRONMENT` | `development` \| `test` \| `production` |

Copier `.env.example` vers `.env`.

## Démarrage local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Docker

```bash
docker compose up --build
```

## Endpoints

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/health` | Santé du service (`status`, `timestamp`) |
| `POST` | `/api/nutrition/analyze` | Analyse nutrition (stub) |
| `POST` | `/api/recommendations/workout` | Recommandation sport (stub) |

## OpenAPI

- Swagger UI : `http://127.0.0.1:8000/docs`
- OpenAPI JSON : `http://127.0.0.1:8000/openapi.json`

## Tests

```bash
pytest
```

`ENVIRONMENT=test` désactive la connexion MongoDB au démarrage (voir `tests/conftest.py`).

## Suite (EPIC #79)

- Schémas MongoDB (#94)
- Moteur de recommandation (#95–#98)
- Intégration NestJS (#99 sur le dépôt `backend`)
