from unittest.mock import AsyncMock, MagicMock, patch

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
async def test_feedback_requires_api_key():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recommendations/workout/507f1f77bcf86cd799439011/feedback",
            json={"rating": 4},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_feedback_validation_422():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recommendations/workout/test-program-id/feedback",
            headers=HEADERS,
            json={"rating": 10},
        )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feedback_submitted_in_test_mode():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recommendations/workout/test-program-id/feedback",
            headers=HEADERS,
            json={
                "rating": 5,
                "tropFacile": True,
                "tropDifficile": False,
                "exercicesProblematiques": ["squat-pdc"],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["programId"] == "test-program-id"
    assert data["feedbackId"]
    assert data["profileNiveau"] == "intermediaire"


@pytest.mark.asyncio
async def test_feedback_program_not_found_with_mongodb():
    with patch("app.services.workout_feedback_service.settings") as mock_settings:
        mock_settings.skip_mongodb_on_startup = False
        with patch(
            "app.services.workout_feedback_service.database.ping_mongodb",
            new_callable=AsyncMock,
            return_value=True,
        ):
            mock_collection = MagicMock()
            mock_collection.find_one = AsyncMock(return_value=None)
            mock_db = MagicMock()
            mock_db.__getitem__ = MagicMock(return_value=mock_collection)
            with patch(
                "app.services.workout_feedback_service.database.get_database",
                return_value=mock_db,
            ):

                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://test",
                ) as client:
                    response = await client.post(
                        "/recommendations/workout/507f1f77bcf86cd799439011/feedback",
                        headers=HEADERS,
                        json={"rating": 3},
                    )

                assert response.status_code == 404
                assert response.json()["detail"] == "PROGRAM_NOT_FOUND"
