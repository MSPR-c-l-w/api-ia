"""Construction du schéma OpenAPI 3.1 (EPIC #79 #100)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.config import settings
from app.contexts.nutrition.presentation.schemas import (
    MealPlanRequest,
    MealPlanResponse,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)
from app.contexts.workout.presentation.schemas import (
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
)
from app.models.schemas import HealthResponse
from app.openapi_config import (
    OPENAPI_CONTACT,
    OPENAPI_DESCRIPTION,
    OPENAPI_SERVERS,
    OPENAPI_TAGS,
)


def _schema(model: type[BaseModel]) -> dict[str, Any]:
    return model.model_json_schema(ref_template="#/components/schemas/{model}")


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def build_openapi_schema() -> dict[str, Any]:
    """Génère le document OpenAPI complet."""
    components: dict[str, Any] = {"schemas": {}}
    for model in (
        HealthResponse,
        NutritionAnalysisRequest,
        NutritionAnalysisResponse,
        MealPlanRequest,
        MealPlanResponse,
        WorkoutProgramRequest,
        WorkoutProgramResponse,
        WorkoutFeedbackRequest,
        WorkoutFeedbackResponse,
    ):
        schema = _schema(model)
        defs = schema.pop("$defs", {})
        components["schemas"][model.__name__] = schema
        components["schemas"].update(defs)

    components["securitySchemes"] = {
        "ApiKeyAuth": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
            "description": "Clé partagée backend NestJS ↔ micro-service",
        },
    }

    json_content = lambda name: {  # noqa: E731
        "application/json": {"schema": _ref(name)},
    }

    return {
        "openapi": "3.1.0",
        "info": {
            "title": settings.api_title,
            "version": settings.api_version,
            "description": OPENAPI_DESCRIPTION,
            "contact": OPENAPI_CONTACT,
        },
        "servers": OPENAPI_SERVERS,
        "tags": OPENAPI_TAGS,
        "paths": {
            "/health": {
                "get": {
                    "tags": ["health"],
                    "summary": "Sonde de santé",
                    "description": "Vérifie que l'API répond. Aucune authentification requise.",
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": json_content("HealthResponse"),
                        },
                    },
                },
            },
            "/ai/nutrition/analyze": {
                "post": {
                    "tags": ["nutrition"],
                    "summary": "Analyser un repas (vision + recommandations)",
                    "description": (
                        "Analyse nutritionnelle à partir d'une image (URL ou base64) et de l'objectif "
                        "utilisateur. Orchestre la détection d'aliments (Google Vision), "
                        "le calcul des macros, la détection des déséquilibres et la génération de "
                        "recommandations personnalisées. Les appels IA sont mis en cache (TTL 1 h "
                        "pour la vision, 24 h pour le LLM) pour limiter les coûts et le rate limiting."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": json_content("NutritionAnalysisRequest"),
                    },
                    "responses": {
                        "200": {
                            "description": "Analyse réussie — aliments, macros, déséquilibres et conseils",
                            "content": json_content("NutritionAnalysisResponse"),
                        },
                        "400": {"description": "Paramètres manquants ou invalides"},
                        "413": {"description": "Image trop volumineuse (max 10 MB)"},
                        "422": {
                            "description": "Corps de requête invalide (validation Pydantic)"
                        },
                        "503": {
                            "description": (
                                "Tous les providers vision sont indisponibles. "
                                "Le service répond en mode stub si les providers IA sont absents."
                            ),
                        },
                    },
                },
            },
            "/ai/nutrition/meal-plan": {
                "post": {
                    "tags": ["nutrition"],
                    "summary": "Générer un plan repas 7 jours personnalisé",
                    "description": (
                        "Génère un plan hebdomadaire via LLM (Ollama) selon l'objectif, "
                        "les contraintes alimentaires et les allergies. Bascule sur un plan statique "
                        "si le LLM est indisponible (timeout 30 s)."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": json_content("MealPlanRequest"),
                    },
                    "responses": {
                        "200": {
                            "description": "Plan repas 7 jours généré",
                            "content": json_content("MealPlanResponse"),
                        },
                        "400": {"description": "Paramètres manquants ou invalides"},
                        "422": {
                            "description": "Corps de requête invalide (validation Pydantic)"
                        },
                        "503": {
                            "description": (
                                "LLM indisponible — le service bascule automatiquement "
                                "sur le plan statique de substitution."
                            ),
                        },
                    },
                },
            },
            "/api/nutrition/analyze": {
                "post": {
                    "tags": ["nutrition"],
                    "summary": "Analyser un repas (legacy)",
                    "description": "Alias de compatibilité vers `/ai/nutrition/analyze`.",
                    "deprecated": True,
                    "requestBody": {
                        "required": True,
                        "content": json_content("NutritionAnalysisRequest"),
                    },
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": json_content("NutritionAnalysisResponse"),
                        },
                        "422": {"description": "Corps de requête invalide"},
                    },
                },
            },
            "/recommendations/workout": {
                "post": {
                    "tags": ["recommendations"],
                    "summary": "Générer un programme d'entraînement hebdomadaire",
                    "description": (
                        "Construit un programme sur 7 jours selon le profil utilisateur, "
                        "avec rotation anti-répétition et persistance MongoDB."
                    ),
                    "security": [{"ApiKeyAuth": []}],
                    "requestBody": {
                        "required": True,
                        "content": json_content("WorkoutProgramRequest"),
                    },
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": json_content("WorkoutProgramResponse"),
                        },
                        "400": {
                            "description": "Données utilisateur insuffisantes (`INSUFFICIENT_USER_DATA`)"
                        },
                        "401": {
                            "description": "Clé API invalide ou absente (`INVALID_API_KEY`)"
                        },
                        "503": {
                            "description": "MongoDB indisponible (`MONGODB_UNAVAILABLE`)"
                        },
                    },
                },
            },
            "/recommendations/workout/{program_id}/feedback": {
                "post": {
                    "tags": ["recommendations"],
                    "summary": "Soumettre un retour sur un programme généré",
                    "description": (
                        "Enregistre le feedback, met à jour le profil sportif MongoDB "
                        "(niveau, limitations temporaires 30 jours)."
                    ),
                    "security": [{"ApiKeyAuth": []}],
                    "parameters": [
                        {
                            "name": "program_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                            "description": "Identifiant MongoDB du programme (`_id` hex)",
                        },
                    ],
                    "requestBody": {
                        "required": True,
                        "content": json_content("WorkoutFeedbackRequest"),
                    },
                    "responses": {
                        "200": {
                            "description": "Successful Response",
                            "content": json_content("WorkoutFeedbackResponse"),
                        },
                        "404": {
                            "description": "Programme introuvable (`PROGRAM_NOT_FOUND`)"
                        },
                        "401": {
                            "description": "Clé API invalide ou absente (`INVALID_API_KEY`)"
                        },
                        "422": {
                            "description": "Validation du corps de requête échouée"
                        },
                        "503": {
                            "description": "MongoDB indisponible (`MONGODB_UNAVAILABLE`)"
                        },
                    },
                },
            },
        },
        "components": components,
    }


def register_openapi_routes(app) -> None:
    """Expose `/openapi.json` et Swagger UI (`/docs`) hors production."""

    if settings.environment == "production":
        return

    @app.get("/openapi.json")
    def openapi_json():
        from flask import jsonify

        return jsonify(build_openapi_schema())

    @app.get("/docs")
    def swagger_ui():
        from flask import render_template_string

        return render_template_string(
            _SWAGGER_HTML,
            openapi_url="/openapi.json",
        )


_SWAGGER_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8"/>
  <title>HealthAI Coach API</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"/>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    SwaggerUIBundle({ url: "{{ openapi_url }}", dom_id: "#swagger-ui" });
  </script>
</body>
</html>"""
