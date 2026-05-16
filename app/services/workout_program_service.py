from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status

from app.config import settings
from app.models.schemas import (
    WorkoutDayResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
    WorkoutSessionExerciseResponse,
)
from app.models.user_profile_scoring import UserProfileForScoring
from app.models.workout_documents import ProgramDay, WorkoutProgram, WorkoutProgramStatus
from app.services import collections as col
from app.services import database
from app.services.weekly_planner import _session_duration_bounds, generate_weekly_program


def _validate_request(payload: WorkoutProgramRequest) -> UserProfileForScoring:
    if not payload.objectif.strip() or not payload.niveau.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INSUFFICIENT_USER_DATA",
        )
    return UserProfileForScoring(
        objectif=payload.objectif.strip(),
        niveau=payload.niveau.strip(),
        materiel=payload.materiel,
        preferences=payload.preferences,
        limitations=payload.limitations,
    )


async def _ensure_mongodb_available() -> None:
    if settings.skip_mongodb_on_startup:
        return
    if not await database.ping_mongodb():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MONGODB_UNAVAILABLE",
        )


async def _get_recent_exercise_ids(user_id: int, weeks: int = 2) -> list[str]:
    if settings.skip_mongodb_on_startup:
        return []

    db = database.get_database()
    cutoff = datetime.now(UTC) - timedelta(weeks=weeks)
    cursor = db[col.WORKOUT_PROGRAMS].find(
        {"userId": user_id, "generatedAt": {"$gte": cutoff}},
    )

    recent_ids: list[str] = []
    async for document in cursor:
        for day in document.get("programme", []):
            for exercise in day.get("exercices", []):
                exercise_id = exercise.get("id")
                if exercise_id:
                    recent_ids.append(exercise_id)
    return recent_ids


def _estimate_exercise_minutes(planned) -> int:
    if planned.duree is not None:
        return planned.duree
    if planned.sets and planned.reps:
        return max(5, planned.sets * 2)
    return 10


def _build_response(
    program_id: str,
    user_id: int,
    niveau: str,
    programme_days: list[ProgramDay],
) -> WorkoutProgramResponse:
    min_dur, max_dur = _session_duration_bounds(niveau)
    default_session = (min_dur + max_dur) // 2

    days: list[WorkoutDayResponse] = []
    for day in programme_days:
        exercises = [
            WorkoutSessionExerciseResponse(
                id=planned.id,
                sets=planned.sets,
                reps=planned.reps,
                duree=planned.duree,
                estimated_duration_minutes=_estimate_exercise_minutes(planned),
            )
            for planned in day.exercices
        ]
        if exercises:
            session_minutes = sum(ex.estimated_duration_minutes for ex in exercises)
            session_minutes = max(session_minutes, default_session // 2)
        else:
            session_minutes = 0

        days.append(
            WorkoutDayResponse(
                jour=day.jour,
                is_rest_day=len(exercises) == 0,
                estimated_session_minutes=session_minutes,
                exercices=exercises,
            ),
        )

    return WorkoutProgramResponse(
        program_id=program_id,
        user_id=user_id,
        statut=WorkoutProgramStatus.ACTIVE.value,
        programme=days,
        generated_at=datetime.now(UTC),
    )


async def create_workout_program(
    payload: WorkoutProgramRequest,
) -> WorkoutProgramResponse:
    profile = _validate_request(payload)
    await _ensure_mongodb_available()

    recent_ids = await _get_recent_exercise_ids(payload.user_id)
    programme = generate_weekly_program(profile, recent_exercise_ids=recent_ids)

    if not any(day.exercices for day in programme):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INSUFFICIENT_USER_DATA",
        )

    program_doc = WorkoutProgram(
        user_id=payload.user_id,
        programme=programme,
        statut=WorkoutProgramStatus.ACTIVE,
    )

    if settings.skip_mongodb_on_startup:
        program_id = "test-program-id"
    else:
        db = database.get_database()
        result = await db[col.WORKOUT_PROGRAMS].insert_one(
            program_doc.model_dump(by_alias=True),
        )
        program_id = str(result.inserted_id)

    return _build_response(
        program_id,
        payload.user_id,
        profile.niveau,
        programme,
    )
