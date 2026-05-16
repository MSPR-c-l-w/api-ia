from fastapi import APIRouter

from app.models.schemas import RecommendationRequest, RecommendationResponse
from app.services import database

router = APIRouter()


@router.post("/workout", response_model=RecommendationResponse)
async def recommend_workout(
    payload: RecommendationRequest,
) -> RecommendationResponse:
    objective = payload.objective
    level = payload.level
    constraints = payload.constraints
    equipment = payload.equipment
    duration = payload.duration_minutes

    knee_safe = "mal au genou" in [item.lower() for item in constraints]

    exercises: list[dict] = [
        {
            "name": "marche rapide",
            "duration_minutes": 10,
            "difficulty": level,
            "tags": ["cardio", "sans materiel", "faible impact"],
        },
        {
            "name": "pont fessier",
            "repetitions": "3 x 12",
            "difficulty": level,
            "tags": ["renforcement", "faible impact"],
        },
        {
            "name": "gainage",
            "repetitions": "3 x 30 sec",
            "difficulty": level,
            "tags": ["core", "sans materiel"],
        },
    ]

    if not knee_safe:
        exercises.append(
            {
                "name": "squats poids du corps",
                "repetitions": "3 x 10",
                "difficulty": level,
                "tags": ["jambes", "sans materiel"],
            }
        )

    mongo_ok = await database.ping_mongodb()

    return RecommendationResponse(
        session_name=f"session_{objective}_{level}",
        exercises=exercises,
        rationale=[
            f"Programme genere pour un objectif de {objective}.",
            f"Duree cible: {duration} minutes.",
            f"Contraintes prises en compte: {', '.join(constraints) if constraints else 'aucune'}.",
            f"Materiel disponible: {', '.join(equipment) if equipment else 'aucun'}.",
        ],
        storage={
            "engine": "mongodb",
            "status": "connected" if mongo_ok else "disconnected",
        },
    )
