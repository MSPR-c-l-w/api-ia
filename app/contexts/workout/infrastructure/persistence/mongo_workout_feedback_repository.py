from datetime import UTC, datetime, timedelta

from app.config import settings
from app.contexts.workout.domain.entities.workout_program import WorkoutFeedback
from app.contexts.workout.domain.repositories.protocols import WorkoutFeedbackRepository
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database


class MongoWorkoutFeedbackRepository(WorkoutFeedbackRepository):
    async def save(self, feedback: WorkoutFeedback) -> str:
        if settings.skip_mongodb_on_startup:
            return "test-feedback-id"
        db = database.get_database()
        result = await db[col.WORKOUT_FEEDBACKS].insert_one(
            feedback.model_dump(by_alias=True),
        )
        return str(result.inserted_id)

    async def count_recent_trop_facile(
        self, user_id: int, *, window_days: int = 30
    ) -> int:
        if settings.skip_mongodb_on_startup:
            return 0

        db = database.get_database()
        cutoff = datetime.now(UTC) - timedelta(days=window_days)
        return await db[col.WORKOUT_FEEDBACKS].count_documents(
            {
                "userId": user_id,
                "tropFacile": True,
                "createdAt": {"$gte": cutoff},
            },
        )
