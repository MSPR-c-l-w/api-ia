"""Tests du schéma OpenAPI et des routes de documentation."""

from unittest.mock import patch

from flask import Flask

from app.presentation.openapi import build_openapi_schema, register_openapi_routes


def test_build_schema_has_core_sections():
    schema = build_openapi_schema()

    assert schema["openapi"] == "3.1.0"
    assert "/health" in schema["paths"]
    assert "/recommendations/workout" in schema["paths"]
    assert "ApiKeyAuth" in schema["components"]["securitySchemes"]
    # Les modèles Pydantic sont injectés dans components.schemas.
    assert "WorkoutProgramResponse" in schema["components"]["schemas"]


def test_openapi_json_route(client):
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.get_json()["openapi"] == "3.1.0"


def test_docs_route_serves_swagger(client):
    response = client.get("/docs")

    assert response.status_code == 200
    assert b"swagger-ui" in response.data


def test_routes_not_registered_in_production():
    with patch("app.presentation.openapi.settings") as mock_settings:
        mock_settings.environment = "production"
        app = Flask(__name__)
        register_openapi_routes(app)

    rules = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/openapi.json" not in rules
    assert "/docs" not in rules
