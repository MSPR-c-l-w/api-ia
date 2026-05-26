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

    assert data["modelStatus"] == "stub_ready_for_huggingface"
    assert isinstance(data["detectedFoods"], list)
    assert data["detectedFoods"][0]["label"]
    assert data["estimatedCalories"] > 0
    assert set(data["estimatedMacros"].keys()) == {"proteins_g", "carbs_g", "fats_g", "fibers_g"}
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
    assert data["days"][0]["snack"] is not None  # collation fournie (aliment réel du catalogue)


def test_nutrition_legacy_analyze_endpoint_still_available(client):
    response = client.post(
        "/api/nutrition/analyze",
        json={
            "imageUrl": "https://example.com/meal.jpg",
            "userGoal": "equilibre",
        },
    )

    assert response.status_code == 200
