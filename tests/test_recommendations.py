from unittest.mock import AsyncMock, PropertyMock, patch

from app.config import settings

API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


def test_workout_requires_api_key(client):
    response = client.post(
        "/recommendations/workout",
        json={
            "userId": 1,
            "objectif": "renforcement",
            "niveau": "debutant",
            "materiel": [],
            "preferences": [],
            "limitations": ["mal au genou"],
        },
    )

    assert response.status_code == 401


def test_workout_invalid_api_key(client):
    response = client.post(
        "/recommendations/workout",
        headers={"X-API-Key": "wrong"},
        json={
            "userId": 1,
            "objectif": "renforcement",
            "niveau": "debutant",
        },
    )

    assert response.status_code == 401


def test_workout_generates_weekly_program(client):
    response = client.post(
        "/recommendations/workout",
        headers=HEADERS,
        json={
            "userId": 42,
            "objectif": "renforcement",
            "niveau": "debutant",
            "materiel": [],
            "preferences": ["faible impact"],
            "limitations": ["mal au genou"],
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["userId"] == 42
    assert data["statut"] == "ACTIVE"
    assert len(data["programme"]) == 7
    assert data["programId"]

    training_days = [d for d in data["programme"] if not d["isRestDay"]]
    assert len(training_days) >= 1

    for day in data["programme"]:
        if day["isRestDay"]:
            assert day["exercices"] == []
            assert day["estimatedSessionMinutes"] == 0
        else:
            for exercise in day["exercices"]:
                assert "id" in exercise
                assert "estimatedDurationMinutes" in exercise

    exercise_ids = [
        ex["id"] for day in data["programme"] for ex in day["exercices"]
    ]
    assert "squat-pdc" not in exercise_ids
    assert len(exercise_ids) == len(set(exercise_ids))


def test_workout_returns_400_when_data_insufficient(client):
    response = client.post(
        "/recommendations/workout",
        headers=HEADERS,
        json={
            "userId": 1,
            "objectif": "   ",
            "niveau": "debutant",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["detail"] == "INSUFFICIENT_USER_DATA"


def test_workout_returns_503_when_mongodb_unavailable(client):
    with (
        patch.object(
            type(settings),
            "skip_mongodb_on_startup",
            new_callable=PropertyMock,
            return_value=False,
        ),
        patch(
            "app.contexts.workout.infrastructure.persistence.mongo_workout_program_repository.database.ping_mongodb",
            new_callable=AsyncMock,
            return_value=False,
        ),
    ):
        response = client.post(
            "/recommendations/workout",
            headers=HEADERS,
            json={
                "userId": 1,
                "objectif": "renforcement",
                "niveau": "debutant",
            },
        )

    assert response.status_code == 503
