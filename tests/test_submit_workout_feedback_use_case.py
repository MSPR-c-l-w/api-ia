"""Tests unitaires du use case SubmitWorkoutFeedback (mode non-test).

On instancie le use case directement avec des dépôts factices implémentant les
Protocol ports, et on patche ``database.ping_mongodb`` pour simuler la
disponibilité de MongoDB sans base réelle.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.contexts.workout.application.use_cases.submit_workout_feedback import (
    TEMP_LIMITATION_PREFIX,
    SubmitWorkoutFeedbackUseCase,
)
from app.contexts.workout.domain.entities.workout_program import UserFitnessProfile
from app.contexts.workout.presentation.schemas import WorkoutFeedbackRequest
from app.shared.application.exceptions import (
    MongoUnavailableError,
    ProgramNotFoundError,
)

PROGRAM_ID = "507f1f77bcf86cd799439011"


class FakeProgramRepo:
    def __init__(self, program: dict | None = None) -> None:
        self._program = program

    async def find_raw_by_id(self, program_id: str):
        return self._program


class FakeFeedbackRepo:
    def __init__(self, recent_trop_facile: int = 0) -> None:
        self.saved: list = []
        self._recent = recent_trop_facile

    async def save(self, feedback) -> str:
        self.saved.append(feedback)
        return "feedback-123"

    async def count_recent_trop_facile(self, user_id: int, *, window_days: int = 30):
        return self._recent


class FakeProfileRepo:
    def __init__(self, profile: UserFitnessProfile | None = None) -> None:
        self._profile = profile
        self.upserted: UserFitnessProfile | None = None

    async def find_by_user_id(self, user_id: int):
        return self._profile

    async def upsert(self, profile: UserFitnessProfile) -> None:
        self.upserted = profile


def _make_use_case(
    *,
    program: dict | None = None,
    profile: UserFitnessProfile | None = None,
    recent_trop_facile: int = 0,
) -> tuple[SubmitWorkoutFeedbackUseCase, FakeFeedbackRepo, FakeProfileRepo]:
    feedbacks = FakeFeedbackRepo(recent_trop_facile=recent_trop_facile)
    profiles = FakeProfileRepo(profile=profile)
    use_case = SubmitWorkoutFeedbackUseCase(
        program_repository=FakeProgramRepo(program=program),
        feedback_repository=feedbacks,
        profile_repository=profiles,
        test_mode=False,
    )
    return use_case, feedbacks, profiles


def _mongo_up():
    return patch(
        "app.shared.infrastructure.database.ping_mongodb",
        new_callable=AsyncMock,
        return_value=True,
    )


# ---------------------------------------------------------------------------
# Mode test (court-circuit)
# ---------------------------------------------------------------------------


async def test_test_mode_bumps_level_when_trop_facile():
    use_case = SubmitWorkoutFeedbackUseCase(
        FakeProgramRepo(), FakeFeedbackRepo(), FakeProfileRepo(), test_mode=True
    )
    payload = WorkoutFeedbackRequest(rating=5, tropFacile=True)

    result = await use_case.execute(PROGRAM_ID, payload)

    assert result.feedback_id == "test-feedback-id"
    assert result.program_id == PROGRAM_ID
    assert result.profile_niveau == "intermediaire"


async def test_test_mode_keeps_level_when_not_trop_facile():
    use_case = SubmitWorkoutFeedbackUseCase(
        FakeProgramRepo(), FakeFeedbackRepo(), FakeProfileRepo(), test_mode=True
    )
    result = await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))

    assert result.profile_niveau == "debutant"


# ---------------------------------------------------------------------------
# Mode réel — erreurs
# ---------------------------------------------------------------------------


async def test_raises_when_mongo_unavailable():
    use_case, _, _ = _make_use_case()
    with (
        patch(
            "app.shared.infrastructure.database.ping_mongodb",
            new_callable=AsyncMock,
            return_value=False,
        ),
        pytest.raises(MongoUnavailableError),
    ):
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))


async def test_raises_when_program_not_found():
    use_case, _, _ = _make_use_case(program=None)
    with _mongo_up(), pytest.raises(ProgramNotFoundError):
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))


# ---------------------------------------------------------------------------
# Mode réel — chemins nominaux
# ---------------------------------------------------------------------------


async def test_creates_default_profile_when_none_exists():
    use_case, feedbacks, profiles = _make_use_case(program={"userId": 42}, profile=None)
    with _mongo_up():
        result = await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=4))

    assert result.feedback_id == "feedback-123"
    assert result.user_id == 42
    assert result.profile_niveau == "debutant"
    assert len(feedbacks.saved) == 1
    # Un profil par défaut a été créé puis persisté avec un évènement feedback.
    assert profiles.upserted is not None
    assert profiles.upserted.user_id == 42
    assert any(e["type"] == "feedback" for e in profiles.upserted.historique)


async def test_problematic_exercises_added_as_temporary_limitations():
    use_case, _, profiles = _make_use_case(program={"userId": 7})
    payload = WorkoutFeedbackRequest(
        rating=2, exercicesProblematiques=["squat-pdc", "burpees"]
    )
    with _mongo_up():
        await use_case.execute(PROGRAM_ID, payload)

    limitations = profiles.upserted.limitations
    assert f"{TEMP_LIMITATION_PREFIX}squat-pdc" in limitations
    assert f"{TEMP_LIMITATION_PREFIX}burpees" in limitations
    assert any(
        e["type"] == "temporary_limitation" for e in profiles.upserted.historique
    )


async def test_trop_facile_repeated_bumps_level():
    profile = UserFitnessProfile(user_id=7, objectif="renforcement", niveau="debutant")
    use_case, _, profiles = _make_use_case(
        program={"userId": 7}, profile=profile, recent_trop_facile=2
    )
    with _mongo_up():
        result = await use_case.execute(
            PROGRAM_ID, WorkoutFeedbackRequest(rating=5, tropFacile=True)
        )

    assert result.profile_niveau == "intermediaire"
    assert any(
        e["type"] == "level_adjustment" and e["to"] == "intermediaire"
        for e in profiles.upserted.historique
    )


async def test_trop_facile_not_repeated_keeps_level():
    profile = UserFitnessProfile(user_id=7, objectif="renforcement", niveau="debutant")
    use_case, _, profiles = _make_use_case(
        program={"userId": 7}, profile=profile, recent_trop_facile=1
    )
    with _mongo_up():
        result = await use_case.execute(
            PROGRAM_ID, WorkoutFeedbackRequest(rating=5, tropFacile=True)
        )

    assert result.profile_niveau == "debutant"
    assert not any(
        e["type"] == "level_adjustment" for e in profiles.upserted.historique
    )


async def test_athlete_level_does_not_bump_past_max():
    profile = UserFitnessProfile(user_id=7, objectif="renforcement", niveau="athlete")
    use_case, _, profiles = _make_use_case(
        program={"userId": 7}, profile=profile, recent_trop_facile=5
    )
    with _mongo_up():
        result = await use_case.execute(
            PROGRAM_ID, WorkoutFeedbackRequest(rating=5, tropFacile=True)
        )

    assert result.profile_niveau == "athlete"


async def test_expired_temporary_limitation_is_pruned():
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    profile = UserFitnessProfile(
        user_id=7,
        objectif="renforcement",
        niveau="debutant",
        limitations=[f"{TEMP_LIMITATION_PREFIX}old-exo", "mal au genou"],
        historique=[
            {
                "type": "temporary_limitation",
                "exerciseIds": ["old-exo"],
                "expiresAt": past,
            }
        ],
    )
    use_case, _, profiles = _make_use_case(program={"userId": 7}, profile=profile)
    with _mongo_up():
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))

    limitations = profiles.upserted.limitations
    # La limitation temporaire expirée est supprimée, la permanente conservée.
    assert f"{TEMP_LIMITATION_PREFIX}old-exo" not in limitations
    assert "mal au genou" in limitations


async def test_active_temporary_limitation_is_kept():
    future = (datetime.now(UTC) + timedelta(days=10)).isoformat()
    profile = UserFitnessProfile(
        user_id=7,
        objectif="renforcement",
        niveau="debutant",
        limitations=[f"{TEMP_LIMITATION_PREFIX}active-exo"],
        historique=[
            {
                "type": "temporary_limitation",
                "exerciseIds": ["active-exo"],
                "expiresAt": future,
            }
        ],
    )
    use_case, _, profiles = _make_use_case(program={"userId": 7}, profile=profile)
    with _mongo_up():
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))

    assert f"{TEMP_LIMITATION_PREFIX}active-exo" in profiles.upserted.limitations


async def test_prune_ignores_event_without_expiry():
    # Évènement temporary_limitation sans expiresAt → ignoré (la limitation tombe).
    profile = UserFitnessProfile(
        user_id=7,
        objectif="renforcement",
        niveau="debutant",
        limitations=[f"{TEMP_LIMITATION_PREFIX}orphan"],
        historique=[{"type": "temporary_limitation", "exerciseIds": ["orphan"]}],
    )
    use_case, _, profiles = _make_use_case(program={"userId": 7}, profile=profile)
    with _mongo_up():
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))

    assert f"{TEMP_LIMITATION_PREFIX}orphan" not in profiles.upserted.limitations


async def test_prune_handles_naive_expiry_datetime():
    # expiresAt sans fuseau horaire (datetime naïf) doit être traité comme UTC.
    future_naive = (
        (datetime.now(UTC) + timedelta(days=5)).replace(tzinfo=None).isoformat()
    )
    profile = UserFitnessProfile(
        user_id=7,
        objectif="renforcement",
        niveau="debutant",
        limitations=[f"{TEMP_LIMITATION_PREFIX}naive-exo"],
        historique=[
            {
                "type": "temporary_limitation",
                "exerciseIds": ["naive-exo"],
                "expiresAt": future_naive,
            }
        ],
    )
    use_case, _, profiles = _make_use_case(program={"userId": 7}, profile=profile)
    with _mongo_up():
        await use_case.execute(PROGRAM_ID, WorkoutFeedbackRequest(rating=3))

    assert f"{TEMP_LIMITATION_PREFIX}naive-exo" in profiles.upserted.limitations
