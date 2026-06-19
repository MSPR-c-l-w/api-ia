def test_nutrition_analyze_ai_endpoint(client):
    response = client.post(
        "/ai/nutrition/analyze",
        json={
            "imageUrl": "https://example.com/meal.jpg",
            "userGoal": "perte_de_poids",
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["modelStatus"] == "vision_stub"
    assert isinstance(data["detectedFoods"], list)
    assert data["detectedFoods"][0]["label"]
    assert data["estimatedCalories"] > 0
    assert set(data["estimatedMacros"].keys()) == {
        "proteins_g",
        "carbs_g",
        "fats_g",
        "fibers_g",
    }
    assert data["imbalanceStatus"] in ("EQUILIBRE", "DESEQUILIBRE")
    assert isinstance(data["nutrientDetails"], list)
    assert len(data["nutrientDetails"]) > 0
    assert isinstance(data["feedback"], list)
    assert len(data["feedback"]) > 0


def test_nutrition_meal_plan_endpoint(client):
    response = client.post(
        "/ai/nutrition/meal-plan",
        json={
            "userGoal": "perte_de_poids",
            "dietaryConstraints": ["vegetarien"],
            "allergies": ["arachide"],
            "dailyCaloriesTarget": 1800,
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["modelStatus"] in ("composer_active", "stub_ready_for_llm")
    assert data["userGoal"] == "perte_de_poids"
    assert len(data["days"]) == 7
    assert 500 <= data["days"][0]["estimatedCalories"] <= 5000
    assert (
        data["days"][0]["snack"] is not None
    )  # collation fournie (aliment réel du catalogue)


HEADERS = {"X-API-Key": "test-api-key"}


def test_analyze_photo_requires_api_key(client):
    response = client.post(
        "/ai/nutrition/analyze-photo",
        json={"imageUrl": "https://example.com/meal.jpg", "userId": 42},
    )

    assert response.status_code == 401


def test_analyze_photo_rejects_wrong_api_key(client):
    response = client.post(
        "/ai/nutrition/analyze-photo",
        json={"imageUrl": "https://example.com/meal.jpg", "userId": 42},
        headers={"X-API-Key": "wrong"},
    )

    assert response.status_code == 401


def test_analyze_photo_returns_backend_contract(client):
    response = client.post(
        "/ai/nutrition/analyze-photo",
        json={"imageUrl": "https://example.com/meal.jpg", "userId": 42},
        headers=HEADERS,
    )

    assert response.status_code == 200
    data = response.get_json()

    # Contrat strictement aligné sur FoodAnalysisResult (backend NestJS).
    assert data["imageUrl"] == "https://example.com/meal.jpg"
    assert isinstance(data["alimentsDetectes"], list)
    assert len(data["alimentsDetectes"]) > 0
    first = data["alimentsDetectes"][0]
    assert set(first.keys()) == {"name", "quantityG", "confidence"}
    assert first["name"]
    assert 0 <= first["confidence"] <= 1
    assert set(data["macros"].keys()) == {"calories", "proteinG", "carbsG", "fatG"}
    assert data["macros"]["calories"] > 0
    assert isinstance(data["suggestions"], list)
    assert data["modelStatus"]


def test_nutrition_legacy_analyze_endpoint_still_available(client):
    response = client.post(
        "/api/nutrition/analyze",
        json={
            "imageUrl": "https://example.com/meal.jpg",
            "userGoal": "equilibre",
        },
    )

    assert response.status_code == 200
