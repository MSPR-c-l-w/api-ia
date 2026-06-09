"""
Seed MongoDB — collections WorkoutProgram, UserFitnessProfile, WorkoutFeedback.

Les profils fitness sont construits depuis les vrais HealthProfile du backend NestJS :
  - niveau  <- physical_activity_level
  - objectif <- BMI (perte_de_poids / prise_de_masse / renforcement / equilibre)

Usage:
    python scripts/seed_mongodb.py
"""

import asyncio
import os
import sys
from datetime import UTC, datetime

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings
from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService
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

_ACTIVITY_TO_NIVEAU = {
    "sedentary": "debutant",
    "lightly_active": "debutant",
    "moderately_active": "intermediaire",
    "very_active": "avance",
    "extra_active": "athlete",
}


def _objectif_from_bmi(bmi: float | None) -> str:
    if bmi is None:
        return "equilibre"
    if bmi >= 25.0:
        return "perte_de_poids"
    if bmi < 18.5:
        return "prise_de_masse"
    return "renforcement"


def fetch_health_profiles() -> list[dict]:
    """Récupère tous les HealthProfile depuis le backend NestJS."""
    if not settings.backend_service_email or not settings.backend_service_password:
        print(
            "BACKEND_SERVICE_EMAIL/PASSWORD non configures -- fallback sur profils par defaut"
        )
        return []

    auth = BackendAuthService(
        backend_url=settings.backend_url,
        email=settings.backend_service_email,
        password=settings.backend_service_password,
    )
    token = auth.get_token()

    url = settings.backend_url.rstrip("/") + "/health-profile"
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        data = resp.json()

    profiles = data if isinstance(data, list) else data.get("data", [])
    print(f"OK {len(profiles)} health profiles recuperes depuis le backend.")
    return profiles


def _profile_from_health(hp: dict) -> dict:
    niveau = _ACTIVITY_TO_NIVEAU.get(
        hp.get("physical_activity_level") or "", "debutant"
    )
    objectif = _objectif_from_bmi(hp.get("bmi"))
    doc = UserFitnessProfile(
        user_id=hp["user_id"],
        objectif=objectif,
        niveau=niveau,
        materiel=[],
        preferences=[],
        limitations=[],
        historique=[
            {"event": "seed_from_health_profile", "at": datetime.now(UTC).isoformat()}
        ],
    )
    return doc.model_dump(by_alias=True)


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


async def seed() -> None:
    client = AsyncIOMotorClient(settings.mongodb_uri)
    database = client.get_default_database()

    await client.admin.command("ping")
    await ensure_indexes(database)

    health_profiles = fetch_health_profiles()

    if not health_profiles:
        print("Aucun health profile -- seed annule.")
        client.close()
        return

    program_ids: list[str] = []

    for hp in health_profiles:
        user_id = hp.get("user_id")
        if not user_id:
            continue

        await database[col.USER_FITNESS_PROFILES].update_one(
            {"userId": user_id},
            {"$set": _profile_from_health(hp)},
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
                exercices_problematiques=[],
            ).model_dump(by_alias=True),
        )

    print(
        f"Seed OK -- {len(health_profiles)} profils, "
        f"{len(program_ids)} programmes, {len(health_profiles)} feedbacks",
    )
    client.close()


if __name__ == "__main__":
    asyncio.run(seed())
