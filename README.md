# HealthAI Coach API (api-ia)

Micro-service **FastAPI** + **MongoDB** (Motor) pour l'analyse nutritionnelle et les recommandations sportives IA.

Partie de l'[EPIC #79](https://github.com/MSPR-c-l-w/backend/issues/79) (issues suivies sur le dépôt `backend`).

## Prérequis

- **Python 3.12+**
- **MongoDB 7** (local ou via Docker)
- Clé API partagée avec le backend NestJS (`BACKEND_API_KEY` = `WORKOUT_SERVICE_API_KEY`)

## Structure

```text
app/
  main.py
  config.py
  openapi_config.py
  routers/
  models/
  services/
docs/
  mongodb-schema.md
openapi.json          # export versionné (scripts/export_openapi.py)
scripts/
  export_openapi.py
  seed_mongodb.py
tests/
docker-compose.yml
Dockerfile
```

## Variables d'environnement

| Variable | Description |
|----------|-------------|
| `MONGODB_URI` | URI MongoDB (ex. `mongodb://localhost:27017/healthai_coach`) |
| `BACKEND_API_KEY` | Clé partagée avec le backend NestJS — header `X-API-Key` sur `/recommendations/*` |
| `PORT` | Port HTTP (défaut `8000`) |
| `ENVIRONMENT` | `development` \| `test` \| `production` — en `production`, `/docs` est désactivé |
| `SECRET_KEY` | Clé interne (réservée évolutions futures) |

Copier `.env.example` vers `.env`.

## Démarrage local

```bash
python -m venv .venv
.venv\Scripts\activate   # Linux/macOS : source .venv/bin/activate
pip install -r requirements.txt
python run.py
```

API : http://127.0.0.1:8000

## Docker

```bash
docker compose up --build
```

Services : API (`8000`) + MongoDB (`27017`).

## Endpoints

| Méthode | Chemin | Auth | Description |
|---------|--------|------|-------------|
| `GET` | `/health` | — | Santé du service |
| `POST` | `/api/nutrition/analyze` | — | Analyse nutrition (stub) |
| `POST` | `/recommendations/workout` | `X-API-Key` | Programme hebdomadaire |
| `POST` | `/recommendations/workout/{id}/feedback` | `X-API-Key` | Retour utilisateur |

## OpenAPI

- **Swagger UI** (développement) : http://127.0.0.1:8000/docs — sans authentification pour la page ; utiliser **Authorize** avec `X-API-Key` pour tester `/recommendations/*`
- **ReDoc** : http://127.0.0.1:8000/redoc
- **JSON live** : http://127.0.0.1:8000/openapi.json
- **Export versionné** :

```bash
python scripts/export_openapi.py
```

Génère `openapi.json` à la racine (à committer après modification des routes ou schémas).

## Tests

```bash
pytest
```

`ENVIRONMENT=test` désactive la connexion MongoDB au démarrage (voir `tests/conftest.py`).

## Schéma MongoDB

Voir [docs/mongodb-schema.md](docs/mongodb-schema.md).

```bash
python scripts/seed_mongodb.py
```

## Intégration backend (#99)

Le backend NestJS appelle ce service via `WORKOUT_SERVICE_URL` + `WORKOUT_SERVICE_API_KEY` :

- `POST {WORKOUT_SERVICE_URL}/recommendations/workout`
- Référence SQL : `AiWorkoutRecommendation.microservice_ref_id` = `programId` MongoDB
