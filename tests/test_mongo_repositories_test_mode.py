"""Tests unitaires des dépôts Mongo en mode test (court-circuit sans base).

En environnement ``test``, ``settings.skip_mongodb_on_startup`` vaut True : les
dépôts renvoient des stubs sans toucher à MongoDB.
"""

from app.config import settings
from app.contexts.workout.domain.entities.workout_program import (
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


def test_skip_flag_is_active_in_test_env():
    assert settings.skip_mongodb_on_startup is True


async def test_program_repo_stubs():
    repo = MongoWorkoutProgramRepository()

    await repo.ensure_available()  # ne lève pas
    assert await repo.save(WorkoutProgram(user_id=1)) == "test-program-id"
    assert await repo.find_raw_by_id("anything") is None
    assert await repo.get_recent_exercise_ids(1) == []


async def test_feedback_repo_stubs():
    repo = MongoWorkoutFeedbackRepository()

    fb = WorkoutFeedback(program_id="p", user_id=1, rating=4)
    assert await repo.save(fb) == "test-feedback-id"
    assert await repo.count_recent_trop_facile(1) == 0


async def test_profile_repo_stubs():
    repo = MongoFitnessProfileRepository()

    assert await repo.find_by_user_id(1) is None
    # upsert ne lève pas et ne fait rien en mode test.
    await repo.upsert(
        UserFitnessProfile(user_id=1, objectif="renforcement", niveau="debutant")
    )
