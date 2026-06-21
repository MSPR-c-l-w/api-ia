"""Génère des données réelles d'usage (profils + programmes + feedbacks) en
pilotant l'API live (port 8000) et MongoDB, pour que l'entraînement du modèle
de scoring sportif dispose d'échantillons réels en plus du bootstrap
synthétique (cf. docs/model-training-report.md §1).

Important : chaque étape utilise le vrai code applicatif — entités de
domaine (`UserFitnessProfile`), repository Mongo réel, endpoints HTTP réels
du moteur de recommandation (même chemin de code qu'un vrai client) — ce
n'est jamais un insert direct en base qui contournerait la logique métier.

Seule la note de satisfaction (`rating`) est simulée : aucun testeur humain
n'a utilisé l'application ce soir. Elle est dérivée de la même vérité
terrain que le générateur synthétique (`dataset_builder._true_compatibility`
— compatibilité réelle objectif/niveau/matériel/contre-indications) plus un
bruit gaussien, exactement comme `generate_synthetic_samples`. Ce n'est donc
pas un vrai feedback humain, mais un usage réel et bout-en-bout du pipeline
applicatif (génération + persistance + ajustement de profil), ce qui est la
différence avec le dataset 100% en mémoire du bootstrap synthétique.

Usage:
    python scripts/seed_real_workout_feedback.py
"""

from __future__ import annotations

import asyncio
import os
import random
import sys

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.contexts.workout.domain.entities.workout_program import (  # noqa: E402
    UserFitnessProfile,
)
from app.contexts.workout.domain.services.dataset_builder import (  # noqa: E402
    _EQUIPMENT_POOL,
    _LEVELS,
    _LIMITATION_POOL,
    _OBJECTIVES,
    _PREFERENCE_POOL,
    _true_compatibility,
)
from app.contexts.workout.domain.value_objects.user_profile import (  # noqa: E402
    UserProfileForScoring,
)
from app.contexts.workout.infrastructure.backend_exercise_lookup import (  # noqa: E402
    BackendExerciseLookupService,
)
from app.contexts.workout.infrastructure.persistence.mongo_fitness_profile_repository import (  # noqa: E402
    MongoFitnessProfileRepository,
)
from app.shared.infrastructure import database  # noqa: E402

_API_BASE = os.environ.get("API_IA_URL", "http://localhost:8000")
_N_USERS = int(os.environ.get("N_SEED_USERS", "120"))
_BASE_USER_ID = 900_000  # plage dédiée, ne collisionne pas avec de vrais users


async def _fetch_real_catalog_by_id() -> dict[str, object]:
    """Récupère le vrai catalogue d'exercices (table Exercise du backend,
    ETL GitHub JSON) — c'est ce catalogue, pas le fichier statique
    exercises_catalog.py, que `create_workout_program` utilise réellement en
    production (cf. backend_exercise_lookup.py + create_workout_program.py)."""
    if not settings.backend_service_email or not settings.backend_service_password:
        raise RuntimeError(
            "BACKEND_SERVICE_EMAIL / BACKEND_SERVICE_PASSWORD non configurés "
            "(.env) — requis pour authentifier ce script auprès du backend.",
        )

    login = httpx.post(
        f"{settings.backend_url}/auth/login",
        json={
            "email": settings.backend_service_email,
            "password": settings.backend_service_password,
        },
        timeout=10,
    )
    login.raise_for_status()
    token = login.json()["access_token"]

    lookup = BackendExerciseLookupService(
        backend_url=settings.backend_url,
        access_token=token,
    )
    catalog = await lookup.get_catalog()
    return {ex.id: ex for ex in catalog}


def _random_profile(rng: random.Random) -> UserProfileForScoring:
    return UserProfileForScoring(
        objectif=rng.choice(_OBJECTIVES),
        niveau=rng.choice(_LEVELS),
        materiel=rng.sample(_EQUIPMENT_POOL, k=rng.randint(0, 4)),
        preferences=rng.sample(_PREFERENCE_POOL, k=rng.randint(0, 2)),
        limitations=[lim for lim in [rng.choice(_LIMITATION_POOL)] if lim],
    )


def _simulate_rating(
    exercise_ids: list[str],
    profile: UserProfileForScoring,
    catalog_by_id: dict[str, object],
    rng: random.Random,
) -> int:
    scores = [
        _true_compatibility(catalog_by_id[eid], profile)
        for eid in exercise_ids
        if eid in catalog_by_id
    ]
    truth = sum(scores) / len(scores) if scores else 0.5
    noisy = max(0.0, min(1.0, truth + rng.gauss(0, 0.15)))
    return max(1, min(5, round(1 + noisy * 4)))


async def main() -> None:
    await database.connect_mongodb()
    profile_repo = MongoFitnessProfileRepository()
    catalog_by_id = await _fetch_real_catalog_by_id()
    print(f"{len(catalog_by_id)} exercices chargés depuis le backend (catalogue réel).")
    rng = random.Random(20260620)

    created_profiles = created_programs = created_feedbacks = 0

    async with httpx.AsyncClient(base_url=_API_BASE, timeout=15) as client:
        for i in range(_N_USERS):
            user_id = _BASE_USER_ID + i
            profile = _random_profile(rng)

            # 1) Persiste le profil réel (entité de domaine, repository réel).
            await profile_repo.upsert(
                UserFitnessProfile(
                    user_id=user_id,
                    objectif=profile.objectif,
                    niveau=profile.niveau,
                    materiel=profile.materiel,
                    preferences=profile.preferences,
                    limitations=profile.limitations,
                ),
            )
            created_profiles += 1

            # 2) Génère un vrai programme via l'API (même moteur qu'en prod,
            # y compris le modèle ML déjà branché dans recommendation_engine).
            resp = await client.post(
                "/recommendations/workout",
                json={
                    "userId": user_id,
                    "objectif": profile.objectif,
                    "niveau": profile.niveau,
                    "materiel": profile.materiel,
                    "preferences": profile.preferences,
                    "limitations": profile.limitations,
                },
                headers={"X-API-Key": settings.backend_api_key},
            )
            if resp.status_code != 200:
                print(
                    f"user {user_id}: échec génération programme ({resp.status_code})"
                )
                continue
            program = resp.json()
            created_programs += 1

            exercise_ids = [
                ex["id"]
                for day in program.get("programme", [])
                for ex in day.get("exercices", [])
            ]

            # 3) Simule une note plausible (cf. docstring) et l'envoie via le
            # vrai endpoint de feedback, qui ajuste le profil persisté.
            rating = _simulate_rating(exercise_ids, profile, catalog_by_id, rng)
            problematic = (
                [rng.choice(exercise_ids)] if rating <= 2 and exercise_ids else []
            )

            fb_resp = await client.post(
                f"/recommendations/workout/{program['programId']}/feedback",
                json={"rating": rating, "exercicesProblematiques": problematic},
                headers={"X-API-Key": settings.backend_api_key},
            )
            if fb_resp.status_code == 200:
                created_feedbacks += 1

    print(
        f"Profils créés : {created_profiles}, programmes générés : "
        f"{created_programs}, feedbacks soumis : {created_feedbacks}",
    )
    await database.close_mongodb()


if __name__ == "__main__":
    asyncio.run(main())
