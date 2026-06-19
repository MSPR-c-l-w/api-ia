"""Tests des helpers HTTP et des gestionnaires d'erreurs Flask."""

API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


def test_missing_json_body_returns_422(client):
    # parse_json lève une ValidationError quand le corps JSON est absent.
    response = client.post(
        "/recommendations/workout",
        headers={**HEADERS, "Content-Type": "application/json"},
        data="",
    )

    assert response.status_code == 422
    assert "detail" in response.get_json()


def test_unknown_route_returns_404_json(client):
    response = client.get("/route-inexistante")

    assert response.status_code == 404
    assert "detail" in response.get_json()


def test_method_not_allowed_returns_json(client):
    # GET sur une route POST → 405 géré par le handler HTTPException générique.
    response = client.get("/recommendations/workout")

    assert response.status_code == 405
    assert "detail" in response.get_json()
