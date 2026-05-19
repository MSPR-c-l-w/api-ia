"""Métadonnées OpenAPI partagées (EPIC #79 #100)."""

OPENAPI_TAGS = [
    {
        "name": "health",
        "description": "Sonde de disponibilité du micro-service.",
    },
    {
        "name": "nutrition",
        "description": "Analyse nutritionnelle (stub — intégration Hugging Face à venir).",
    },
    {
        "name": "recommendations",
        "description": (
            "Programmes d'entraînement hebdomadaires et feedback utilisateur. "
            "Requiert le header `X-API-Key` (clé partagée avec le backend NestJS)."
        ),
    },
]

OPENAPI_DESCRIPTION = """
Micro-service **HealthAI Coach** : moteur de recommandations sportives et analyse nutrition.

## Authentification inter-services

Les routes `/recommendations/*` exigent le header **`X-API-Key`**, identique à la variable
`BACKEND_API_KEY` côté api-ia et `WORKOUT_SERVICE_API_KEY` côté backend NestJS (#99).

## Persistance

Les programmes et feedbacks sont stockés dans **MongoDB** (`workout_programs`, `workout_feedbacks`,
`user_fitness_profiles`). Voir [docs/mongodb-schema.md](https://github.com/MSPR-c-l-w/api-ia/blob/main/docs/mongodb-schema.md).
"""

OPENAPI_CONTACT = {
    "name": "MSPR-c-l-w",
    "url": "https://github.com/MSPR-c-l-w/api-ia",
}

OPENAPI_SERVERS = [
    {"url": "http://127.0.0.1:8000", "description": "Développement local"},
    {"url": "http://localhost:8000", "description": "Docker Compose (port mappé)"},
]
