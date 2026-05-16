from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(autouse=True)
def api_key_env(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", API_KEY)
    monkeypatch.setenv("ENVIRONMENT", "test")


@pytest.mark.asyncio
async def test_workout_requires_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
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


@pytest.mark.asyncio
async def test_workout_invalid_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recommendations/workout",
            headers={"X-API-Key": "wrong"},
            json={
                "userId": 1,
                "objectif": "renforcement",
                "niveau": "debutant",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_workout_generates_weekly_program():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
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
    data = response.json()
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


@pytest.mark.asyncio
async def test_workout_returns_400_when_data_insufficient():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recommendations/workout",
            headers=HEADERS,
            json={
                "userId": 1,
                "objectif": "   ",
                "niveau": "debutant",
            },
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "INSUFFICIENT_USER_DATA"


@pytest.mark.asyncio
async def test_workout_returns_503_when_mongodb_unavailable():
    with patch(
        "app.services.workout_program_service._ensure_mongodb_available",
        new_callable=AsyncMock,
    ) as mock_ensure:
        mock_ensure.side_effect = __import__(
            "fastapi",
            fromlist=["HTTPException"],
        ).HTTPException(status_code=503, detail="MONGODB_UNAVAILABLE")

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/recommendations/workout",
                headers=HEADERS,
                json={
                    "userId": 1,
                    "objectif": "renforcement",
                    "niveau": "debutant",
                },
            )

    assert response.status_code == 503
