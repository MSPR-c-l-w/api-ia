from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from app.config import settings

API_KEY = "test-api-key"
HEADERS = {"X-API-Key": API_KEY}


def test_feedback_requires_api_key(client):
    response = client.post(
        "/recommendations/workout/507f1f77bcf86cd799439011/feedback",
        json={"rating": 4},
    )

    assert response.status_code == 401


def test_feedback_validation_422(client):
    response = client.post(
        "/recommendations/workout/test-program-id/feedback",
        headers=HEADERS,
        json={"rating": 10},
    )

    assert response.status_code == 422


def test_feedback_submitted_in_test_mode(client):
    response = client.post(
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
    data = response.get_json()
    assert data["programId"] == "test-program-id"
    assert data["feedbackId"]
    assert data["profileNiveau"] == "intermediaire"


def test_feedback_program_not_found_with_mongodb(client):
    with (
        patch.object(
            type(settings),
            "skip_mongodb_on_startup",
            new_callable=PropertyMock,
            return_value=False,
        ),
        patch(
            "app.shared.infrastructure.database.ping_mongodb",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch(
            "app.contexts.workout.infrastructure.persistence.mongo_workout_program_repository.database.get_database",
        ) as mock_get_db,
    ):
        mock_collection = MagicMock()
        mock_collection.find_one = AsyncMock(return_value=None)
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_get_db.return_value = mock_db

        response = client.post(
            "/recommendations/workout/507f1f77bcf86cd799439011/feedback",
            headers=HEADERS,
            json={"rating": 3},
        )

    assert response.status_code == 404
    assert response.get_json()["detail"] == "PROGRAM_NOT_FOUND"
