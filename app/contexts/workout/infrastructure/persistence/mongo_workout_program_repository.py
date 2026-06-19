from datetime import UTC, datetime, timedelta
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from app.config import settings
from app.contexts.workout.domain.entities.workout_program import WorkoutProgram
from app.contexts.workout.domain.repositories.protocols import WorkoutProgramRepository
from app.shared.application.exceptions import (
    MongoUnavailableError,
    ProgramNotFoundError,
)
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database


class MongoWorkoutProgramRepository(WorkoutProgramRepository):
    async def ensure_available(self) -> None:
        if settings.skip_mongodb_on_startup:
            return
        if not await database.ping_mongodb():
            raise MongoUnavailableError()

    async def save(self, program: WorkoutProgram) -> str:
        if settings.skip_mongodb_on_startup:
            return "test-program-id"
        db = database.get_database()
        result = await db[col.WORKOUT_PROGRAMS].insert_one(
            program.model_dump(by_alias=True),
        )
        return str(result.inserted_id)

    async def find_raw_by_id(self, program_id: str) -> dict[str, Any] | None:
        if settings.skip_mongodb_on_startup:
            return None
        if not ObjectId.is_valid(program_id):
            raise ProgramNotFoundError()
        try:
            oid = ObjectId(program_id)
        except (
            InvalidId,
            TypeError,
        ) as exc:  # pragma: no cover - garde défensif (is_valid filtre déjà)
            raise ProgramNotFoundError() from exc

        db = database.get_database()
        return await db[col.WORKOUT_PROGRAMS].find_one({"_id": oid})

    async def get_recent_exercise_ids(
        self, user_id: int, *, weeks: int = 2
    ) -> list[str]:
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
