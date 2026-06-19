"""Tests d'intégration des dépôts MongoDB.

Requièrent une instance MongoDB accessible. Marqués ``integration`` et
automatiquement ignorés (``skip``) si la base est indisponible.

    pytest -m integration            # exécute ces tests
    pytest -m "not integration"      # les ignore (défaut CI unitaire)
"""

import pytest

from app.config import settings
from app.contexts.workout.domain.entities.workout_program import (
    PlannedExercise,
    ProgramDay,
    UserFitnessProfile,
    WorkoutFeedback,
    WorkoutProgram,
)
from app.contexts.workout.infrastructure.persistence.mongo_fitness_profile_repository import (
    MongoFitnessProfileRepository,
)
from app.contexts.workout.infrastructure.persistence.mongo_workout_feedback_repository import (
    MongoWorkoutFeedbackRepository,
)
from app.contexts.workout.infrastructure.persistence.mongo_workout_program_repository import (
    MongoWorkoutProgramRepository,
)
from app.shared.application.exceptions import ProgramNotFoundError
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database

pytestmark = pytest.mark.integration

# Base de test isolée + timeout court pour échouer vite si Mongo est absent.
_TEST_URI = (
    "mongodb://localhost:27017/healthai_coach_test?serverSelectionTimeoutMS=1500"
)


@pytest.fixture
async def mongo_db(monkeypatch):
    # Désactive le court-circuit "test mode" pour viser une vraie base.
    monkeypatch.setattr(settings, "environment", "integration")
    monkeypatch.setattr(settings, "mongodb_uri", _TEST_URI)

    try:
        await database.connect_mongodb()
        available = await database.ping_mongodb()
    except Exception:
        available = False

    if not available:
        await database.close_mongodb()
        pytest.skip("MongoDB indisponible — test d'intégration ignoré")

    db = database.get_database()
    for name in (
        col.WORKOUT_PROGRAMS,
        col.USER_FITNESS_PROFILES,
        col.WORKOUT_FEEDBACKS,
    ):
        await db[name].delete_many({})

    yield db

    for name in (
        col.WORKOUT_PROGRAMS,
        col.USER_FITNESS_PROFILES,
        col.WORKOUT_FEEDBACKS,
    ):
        await db[name].delete_many({})
    await database.close_mongodb()


# ---------------------------------------------------------------------------
# MongoWorkoutProgramRepository
# ---------------------------------------------------------------------------


async def test_program_save_and_find_raw_by_id(mongo_db):
    repo = MongoWorkoutProgramRepository()
    program = WorkoutProgram(
        user_id=42,
        programme=[
            ProgramDay(jour="lundi", exercices=[PlannedExercise(id="squat-pdc")])
        ],
    )

    program_id = await repo.save(program)
    assert program_id and program_id != "test-program-id"

    raw = await repo.find_raw_by_id(program_id)
    assert raw is not None
    assert raw["userId"] == 42


async def test_program_find_unknown_returns_none(mongo_db):
    repo = MongoWorkoutProgramRepository()

    raw = await repo.find_raw_by_id("507f1f77bcf86cd799439011")

    assert raw is None


async def test_program_find_invalid_id_raises(mongo_db):
    repo = MongoWorkoutProgramRepository()

    with pytest.raises(ProgramNotFoundError):
        await repo.find_raw_by_id("pas-un-objectid")


async def test_program_ensure_available_ok(mongo_db):
    repo = MongoWorkoutProgramRepository()

    # Ne lève pas quand la base répond.
    await repo.ensure_available()


async def test_get_recent_exercise_ids(mongo_db):
    repo = MongoWorkoutProgramRepository()
    program = WorkoutProgram(
        user_id=99,
        programme=[
            ProgramDay(
                jour="lundi",
                exercices=[
                    PlannedExercise(id="squat-pdc"),
                    PlannedExercise(id="pont-fessier"),
                ],
            )
        ],
    )
    await repo.save(program)

    recent = await repo.get_recent_exercise_ids(99, weeks=2)

    assert set(recent) == {"squat-pdc", "pont-fessier"}


# ---------------------------------------------------------------------------
# MongoWorkoutFeedbackRepository
# ---------------------------------------------------------------------------


async def test_feedback_save_and_count_recent_trop_facile(mongo_db):
    repo = MongoWorkoutFeedbackRepository()

    fb_id = await repo.save(
        WorkoutFeedback(program_id="p1", user_id=5, rating=5, trop_facile=True)
    )
    assert fb_id and fb_id != "test-feedback-id"
    await repo.save(
        WorkoutFeedback(program_id="p2", user_id=5, rating=5, trop_facile=True)
    )
    # Un feedback "trop facile=False" ne doit pas être compté.
    await repo.save(
        WorkoutFeedback(program_id="p3", user_id=5, rating=3, trop_facile=False)
    )

    count = await repo.count_recent_trop_facile(5, window_days=30)

    assert count == 2


async def test_count_recent_trop_facile_zero_for_unknown_user(mongo_db):
    repo = MongoWorkoutFeedbackRepository()

    assert await repo.count_recent_trop_facile(123456, window_days=30) == 0


# ---------------------------------------------------------------------------
# MongoFitnessProfileRepository
# ---------------------------------------------------------------------------


async def test_profile_upsert_and_find(mongo_db):
    repo = MongoFitnessProfileRepository()
    profile = UserFitnessProfile(
        user_id=77, objectif="renforcement", niveau="debutant", materiel=["tapis"]
    )

    await repo.upsert(profile)
    found = await repo.find_by_user_id(77)

    assert found is not None
    assert found.niveau == "debutant"
    assert found.materiel == ["tapis"]


async def test_profile_upsert_updates_existing(mongo_db):
    repo = MongoFitnessProfileRepository()
    await repo.upsert(
        UserFitnessProfile(user_id=77, objectif="renforcement", niveau="debutant")
    )
    await repo.upsert(
        UserFitnessProfile(user_id=77, objectif="renforcement", niveau="avance")
    )

    found = await repo.find_by_user_id(77)

    assert found.niveau == "avance"
    # Upsert, pas insert : un seul document pour cet utilisateur.
    assert (
        await mongo_db[col.USER_FITNESS_PROFILES].count_documents({"userId": 77}) == 1
    )


async def test_profile_find_unknown_returns_none(mongo_db):
    repo = MongoFitnessProfileRepository()

    assert await repo.find_by_user_id(999999) is None
