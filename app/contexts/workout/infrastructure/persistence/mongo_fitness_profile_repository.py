from app.config import settings
from app.contexts.workout.domain.entities.workout_program import UserFitnessProfile
from app.contexts.workout.domain.repositories.protocols import FitnessProfileRepository
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database


class MongoFitnessProfileRepository(FitnessProfileRepository):
    async def find_by_user_id(self, user_id: int) -> UserFitnessProfile | None:
        if settings.skip_mongodb_on_startup:
            return None
        db = database.get_database()
        raw = await db[col.USER_FITNESS_PROFILES].find_one({"userId": user_id})
        if raw is None:
            return None
        return UserFitnessProfile.model_validate(raw)

    async def upsert(self, profile: UserFitnessProfile) -> None:
        if settings.skip_mongodb_on_startup:
            return
        db = database.get_database()
        await db[col.USER_FITNESS_PROFILES].update_one(
            {"userId": profile.user_id},
            {"$set": profile.model_dump(by_alias=True)},
            upsert=True,
        )
