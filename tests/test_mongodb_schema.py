from datetime import UTC, datetime

import pytest

from app.models.workout_documents import (
    PlannedExercise,
    ProgramDay,
    UserFitnessProfile,
    WorkoutFeedback,
    WorkoutProgram,
    WorkoutProgramStatus,
)


def test_workout_program_serializes_with_mongo_aliases():
    doc = WorkoutProgram(
        user_id=42,
        programme=[
            ProgramDay(
                jour="lundi",
                exercices=[PlannedExercise(id="squat", sets=3, reps=10)],
            ),
        ],
        statut=WorkoutProgramStatus.ACTIVE,
        generated_at=datetime(2026, 5, 16, 12, 0, tzinfo=UTC),
    )

    payload = doc.model_dump(by_alias=True)

    assert payload["userId"] == 42
    assert payload["programme"][0]["jour"] == "lundi"
    assert payload["programme"][0]["exercices"][0]["id"] == "squat"
    assert payload["statut"] == "ACTIVE"
    assert "generatedAt" in payload


def test_user_fitness_profile_schema():
    doc = UserFitnessProfile(
        user_id=1,
        objectif="perte_de_poids",
        niveau="intermediaire",
        materiel=["barre"],
        preferences=["cardio"],
        limitations=[],
    )

    payload = doc.model_dump(by_alias=True)
    assert payload["userId"] == 1
    assert payload["materiel"] == ["barre"]


def test_workout_feedback_schema():
    doc = WorkoutFeedback(
        program_id="665a1b2c3d4e5f6789012345",
        user_id=1,
        rating=5,
        trop_difficile=True,
        exercices_problematiques=["burpees"],
    )

    payload = doc.model_dump(by_alias=True)
    assert payload["programId"] == "665a1b2c3d4e5f6789012345"
    assert payload["tropDifficile"] is True
    assert payload["exercicesProblematiques"] == ["burpees"]


@pytest.mark.asyncio
async def test_ensure_indexes_calls_create_index():
    from unittest.mock import AsyncMock, MagicMock

    from app.services import collections as col
    from app.services.indexes import ensure_indexes

    programs = MagicMock()
    programs.create_index = AsyncMock()
    profiles = MagicMock()
    profiles.create_index = AsyncMock()
    feedbacks = MagicMock()
    feedbacks.create_index = AsyncMock()

    db = MagicMock()
    db.__getitem__.side_effect = lambda name: {
        col.WORKOUT_PROGRAMS: programs,
        col.USER_FITNESS_PROFILES: profiles,
        col.WORKOUT_FEEDBACKS: feedbacks,
    }[name]

    await ensure_indexes(db)

    programs.create_index.assert_awaited_once_with("userId")
    profiles.create_index.assert_awaited_once_with("userId")
    assert feedbacks.create_index.await_count == 2
