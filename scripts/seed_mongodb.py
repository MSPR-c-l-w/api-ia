"""
Seed MongoDB — collections WorkoutProgram, UserFitnessProfile, WorkoutFeedback.

Usage:
    python scripts/seed_mongodb.py
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.models.workout_documents import (
    PlannedExercise,
    ProgramDay,
    UserFitnessProfile,
    WorkoutFeedback,
    WorkoutProgram,
    WorkoutProgramStatus,
)
from app.services import collections as col
from app.services.indexes import ensure_indexes


def _sample_program(user_id: int) -> dict:
    doc = WorkoutProgram(
        user_id=user_id,
        programme=[
            ProgramDay(
                jour="lundi",
                exercices=[
                    PlannedExercise(id="marche-rapide", duree=15),
                    PlannedExercise(id="pont-fessier", sets=3, reps=12),
                ],
            ),
            ProgramDay(
                jour="mercredi",
                exercices=[
                    PlannedExercise(id="gainage", sets=3, duree=1),
                ],
            ),
        ],
        statut=WorkoutProgramStatus.ACTIVE,
        generated_at=datetime.now(UTC),
    )
    return doc.model_dump(by_alias=True)


def _sample_profile(user_id: int) -> dict:
    doc = UserFitnessProfile(
        user_id=user_id,
        objectif="renforcement",
        niveau="debutant",
        materiel=["tapis", "haltères"],
        preferences=["renforcement", "faible impact"],
        limitations=["mal au genou"],
        historique=[{"event": "seed", "at": datetime.now(UTC).isoformat()}],
    )
    return doc.model_dump(by_alias=True)


async def seed() -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    database = client.get_default_database()

    await client.admin.command("ping")
    await ensure_indexes(database)

    user_ids = [1, 2, 3]
    program_ids: list[str] = []

    for user_id in user_ids:
        await database[col.USER_FITNESS_PROFILES].update_one(
            {"userId": user_id},
            {"$set": _sample_profile(user_id)},
            upsert=True,
        )

        result = await database[col.WORKOUT_PROGRAMS].insert_one(
            _sample_program(user_id),
        )
        program_ids.append(str(result.inserted_id))

        await database[col.WORKOUT_FEEDBACKS].insert_one(
            WorkoutFeedback(
                program_id=program_ids[-1],
                user_id=user_id,
                rating=4,
                trop_difficile=False,
                trop_facile=False,
                exercices_problematiques=["squat"],
            ).model_dump(by_alias=True),
        )

    print(
        f"Seed OK — {len(user_ids)} profils, "
        f"{len(program_ids)} programmes, {len(user_ids)} feedbacks",
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
