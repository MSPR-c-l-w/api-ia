import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_workout_recommendation_stub():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/recommendations/workout",
            json={
                "objective": "renforcement",
                "level": "debutant",
                "constraints": ["mal au genou"],
                "equipment": [],
                "duration_minutes": 30,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["session_name"] == "session_renforcement_debutant"
    assert len(data["exercises"]) == 3
    assert data["storage"]["engine"] == "mongodb"
