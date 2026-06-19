"""Vérifie que les modules de compatibilité (legacy) ré-exportent correctement."""

import inspect


def test_services_database_reexports():
    from app.services import database as legacy_db
    from app.shared.infrastructure import database as canonical

    assert legacy_db.connect_mongodb is canonical.connect_mongodb
    assert legacy_db.close_mongodb is canonical.close_mongodb
    assert legacy_db.get_client is canonical.get_client
    assert legacy_db.get_database is canonical.get_database
    assert legacy_db.ping_mongodb is canonical.ping_mongodb


def test_services_workout_program_shim_is_async():
    from app.services.workout_program_service import create_workout_program

    assert inspect.iscoroutinefunction(create_workout_program)


def test_services_workout_feedback_shim_is_async():
    from app.services.workout_feedback_service import submit_workout_feedback

    assert inspect.iscoroutinefunction(submit_workout_feedback)


async def test_workout_program_shim_delegates_to_use_case():
    from app.contexts.workout.presentation.schemas import WorkoutProgramRequest
    from app.services.workout_program_service import create_workout_program

    result = await create_workout_program(
        WorkoutProgramRequest(userId=1, objectif="renforcement", niveau="debutant")
    )

    assert result.user_id == 1
    assert len(result.programme) == 7


async def test_workout_feedback_shim_delegates_to_use_case():
    from app.contexts.workout.presentation.schemas import WorkoutFeedbackRequest
    from app.services.workout_feedback_service import submit_workout_feedback

    # En mode test, le use case court-circuite et renvoie un stub.
    result = await submit_workout_feedback(
        "test-program-id", WorkoutFeedbackRequest(rating=4)
    )

    assert result.program_id == "test-program-id"
    assert result.feedback_id == "test-feedback-id"
