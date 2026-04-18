"""Tests for the biometric meal recommendation endpoint.

Backend HTTP calls are mocked with the `responses` library so tests run
without a running NestJS instance.
"""

import pytest
import responses as resp_mock

from app import create_app

BACKEND_URL = "http://localhost:3000"

MOCK_USER = {
    "id": 1,
    "first_name": "Alice",
    "last_name": "Dupont",
    "email": "alice@example.com",
    "gender": "female",
    "date_of_birth": "1995-06-15T00:00:00.000Z",
    "height": 165.0,
}

MOCK_HEALTH_PROFILE = {
    "id": 1,
    "user_id": 1,
    "weight": 62.0,
    "bmi": 22.8,
    "physical_activity_level": "lightly_active",
    "daily_calories_target": None,
}

MOCK_NUTRITION = {
    "data": [
        {
            "id": 1,
            "name": "Poulet Riz",
            "category": "protein",
            "calories_kcal": 520.0,
            "protein_g": 38.0,
            "carbohydrates_g": 55.0,
            "fat_g": 10.0,
            "fiber_g": 3.0,
            "sugar_g": 2.0,
            "sodium_mg": 380.0,
            "cholesterol_mg": 75.0,
            "meal_type_name": "lunch",
            "water_intake_ml": 200.0,
            "picture_url": None,
        },
        {
            "id": 2,
            "name": "Salade César",
            "category": "vegetarian",
            "calories_kcal": 310.0,
            "protein_g": 12.0,
            "carbohydrates_g": 20.0,
            "fat_g": 22.0,
            "fiber_g": 5.0,
            "sugar_g": 3.0,
            "sodium_mg": 600.0,
            "cholesterol_mg": 40.0,
            "meal_type_name": "lunch",
            "water_intake_ml": 150.0,
            "picture_url": None,
        },
        {
            "id": 3,
            "name": "Burger Maison",
            "category": "beef",
            "calories_kcal": 850.0,
            "protein_g": 42.0,
            "carbohydrates_g": 70.0,
            "fat_g": 38.0,
            "fiber_g": 2.0,
            "sugar_g": 8.0,
            "sodium_mg": 950.0,
            "cholesterol_mg": 110.0,
            "meal_type_name": "lunch",
            "water_intake_ml": 100.0,
            "picture_url": None,
        },
        {
            "id": 4,
            "name": "Bol de Quinoa",
            "category": "vegetarian",
            "calories_kcal": 420.0,
            "protein_g": 18.0,
            "carbohydrates_g": 60.0,
            "fat_g": 12.0,
            "fiber_g": 7.0,
            "sugar_g": 4.0,
            "sodium_mg": 280.0,
            "cholesterol_mg": 0.0,
            "meal_type_name": "lunch",
            "water_intake_ml": 180.0,
            "picture_url": None,
        },
        {
            "id": 5,
            "name": "Saumon Grillé",
            "category": "fish",
            "calories_kcal": 490.0,
            "protein_g": 44.0,
            "carbohydrates_g": 15.0,
            "fat_g": 28.0,
            "fiber_g": 1.0,
            "sugar_g": 1.0,
            "sodium_mg": 320.0,
            "cholesterol_mg": 90.0,
            "meal_type_name": "dinner",
            "water_intake_ml": 200.0,
            "picture_url": None,
        },
    ],
    "total": 5,
}

AUTH_HEADER = {"Authorization": "Bearer test-jwt-token"}


@pytest.fixture
def app():
    application = create_app()
    application.config["TESTING"] = True
    application.config["BACKEND_URL"] = BACKEND_URL
    return application


@pytest.fixture
def client(app):
    with app.test_client() as c:
        yield c


def _register_backend_mocks():
    """Register the three backend endpoints used by /predict."""
    resp_mock.add(resp_mock.GET, f"{BACKEND_URL}/auth/me", json=MOCK_USER, status=200)
    resp_mock.add(
        resp_mock.GET,
        f"{BACKEND_URL}/health-profile/me",
        json=MOCK_HEALTH_PROFILE,
        status=200,
    )
    resp_mock.add(
        resp_mock.GET,
        f"{BACKEND_URL}/nutrition",
        json=MOCK_NUTRITION,
        status=200,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@resp_mock.activate
def test_predict_returns_recommendations(client):
    _register_backend_mocks()
    response = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch", "top_n": 3},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "success"
    assert len(data["recommendations"]) == 3
    assert "nutritional_targets" in data
    assert "user" in data


@resp_mock.activate
def test_predict_exposes_real_user_biometrics(client):
    _register_backend_mocks()
    data = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch"},
        headers=AUTH_HEADER,
    ).get_json()

    user = data["user"]
    assert user["gender"] == "female"
    assert user["weight_kg"] == 62.0
    assert user["height_cm"] == 165.0
    assert user["age"] is not None and user["age"] > 0


@resp_mock.activate
def test_predict_nutritional_targets_are_positive(client):
    _register_backend_mocks()
    targets = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch"},
        headers=AUTH_HEADER,
    ).get_json()["nutritional_targets"]

    assert targets["target_calories"] > 0
    assert targets["target_protein_g"] > 0
    assert targets["target_carbs_g"] > 0
    assert targets["target_fat_g"] > 0


@resp_mock.activate
def test_predict_confidence_scores_in_range(client):
    _register_backend_mocks()
    recs = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch"},
        headers=AUTH_HEADER,
    ).get_json()["recommendations"]

    for rec in recs:
        assert 0 <= rec["confidence_score"] <= 100


@resp_mock.activate
def test_predict_vegetarian_constraint_penalises_meat(client):
    _register_backend_mocks()
    recs = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch", "dietary_constraints": ["vegetarian"], "top_n": 5},
        headers=AUTH_HEADER,
    ).get_json()["recommendations"]

    names = [r["name"] for r in recs]
    veg = {"Salade César", "Bol de Quinoa"}
    meat = {"Burger Maison", "Saumon Grillé"}
    veg_pos = [names.index(n) for n in names if n in veg]
    meat_pos = [names.index(n) for n in names if n in meat]
    if veg_pos and meat_pos:
        assert min(veg_pos) < max(meat_pos)


@resp_mock.activate
def test_predict_respects_top_n(client):
    for n in [1, 2, 5]:
        _register_backend_mocks()
        recs = client.post(
            "/api/recommendations/predict",
            json={"top_n": n},
            headers=AUTH_HEADER,
        ).get_json()["recommendations"]
        assert len(recs) == n


@resp_mock.activate
def test_predict_missing_jwt_returns_401(client):
    response = client.post("/api/recommendations/predict", json={})
    assert response.status_code == 401


@resp_mock.activate
def test_predict_backend_401_propagates(client):
    resp_mock.add(resp_mock.GET, f"{BACKEND_URL}/auth/me", status=401)
    response = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 401


@resp_mock.activate
def test_predict_incomplete_profile_returns_422(client):
    # User missing height and date_of_birth
    resp_mock.add(
        resp_mock.GET,
        f"{BACKEND_URL}/auth/me",
        json={**MOCK_USER, "date_of_birth": None, "height": None},
        status=200,
    )
    resp_mock.add(
        resp_mock.GET,
        f"{BACKEND_URL}/health-profile/me",
        json=MOCK_HEALTH_PROFILE,
        status=200,
    )
    resp_mock.add(resp_mock.GET, f"{BACKEND_URL}/nutrition", json=MOCK_NUTRITION, status=200)

    response = client.post(
        "/api/recommendations/predict",
        json={"meal_type": "lunch"},
        headers=AUTH_HEADER,
    )
    assert response.status_code == 422
    assert "Missing" in response.get_json().get("message", "")


def test_train_endpoint(client):
    response = client.post("/api/recommendations/train")
    assert response.status_code == 200
    assert response.get_json()["status"] == "success"


def test_health_endpoint(client):
    response = client.get("/api/health/")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"

