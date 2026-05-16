from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services import collections as col


async def ensure_indexes(database: AsyncIOMotorDatabase) -> None:
    """Crée les index MongoDB pour les collections EPIC #79."""
    await database[col.WORKOUT_PROGRAMS].create_index("userId")
    await database[col.USER_FITNESS_PROFILES].create_index("userId")
    await database[col.WORKOUT_FEEDBACKS].create_index("userId")
    await database[col.WORKOUT_FEEDBACKS].create_index("programId")
