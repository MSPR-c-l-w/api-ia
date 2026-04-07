# HealthAI Coach API

Initialisation d'un backend Flask structure pour une API IA autour de deux axes:

- analyse nutritionnelle par vision ordinateur
- recommandations sportives multi-criteres

Le projet est initialise avec une architecture simple, extensible, et documentee via OpenAPI.

## Structure

```text
app/
  api/
    health.py
    nutrition.py
    recommendations.py
  __init__.py
  config.py
  extensions.py
  schemas.py
tests/
run.py
requirements.txt
```

## Demarrage

1. Creer un environnement virtuel
2. Installer les dependances
3. Lancer l'API

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Endpoints disponibles

- `GET /api/health/`
- `POST /api/nutrition/analyze`
- `POST /api/recommendations/workout`

## Swagger

Une fois l'application lancee:

- UI Swagger: `http://127.0.0.1:5000/docs/swagger`
- Spec OpenAPI JSON: `http://127.0.0.1:5000/docs/openapi.json`

## Suite du projet

Les endpoints `nutrition` et `recommendations` sont pour l'instant des stubs:

- `nutrition` est pret a recevoir un pipeline Hugging Face pour classifier une image de repas
- `recommendations` est pret a etre branche a un moteur de filtrage + historique MongoDB

## Prochaines etapes conseillees

- brancher un vrai modele Hugging Face pour la classification food
- connecter MongoDB pour stocker l'historique des recommandations
- separer le moteur IA dans un micro-service dedie si tu veux coller a l'architecture MSPR
