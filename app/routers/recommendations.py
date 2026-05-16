from fastapi import APIRouter

from app.models.schemas import RecommendationRequest, RecommendationResponse
from app.models.user_profile_scoring import UserProfileForScoring
from app.services import database
from app.services.recommendation_engine import recommend_exercises

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

    profile = UserProfileForScoring(
        objectif=objective,
        niveau=level,
        materiel=equipment,
        preferences=[],
        limitations=constraints,
    )
    ranked = recommend_exercises(profile, top_n_per_group=2)

    exercises: list[dict] = [
        {
            "id": exercise.id,
            "name": exercise.name,
            "muscle_group": exercise.muscle_group,
            "score": score,
            "difficulty": level,
            "tags": exercise.tags,
        }
        for exercise, score in ranked
    ]

    mongo_ok = await database.ping_mongodb()

    return RecommendationResponse(
        session_name=f"session_{objective}_{level}",
        exercises=exercises,
        rationale=[
            f"Programme genere pour un objectif de {objective} (moteur multi-criteres).",
            f"Duree cible: {duration} minutes.",
            f"Contraintes prises en compte: {', '.join(constraints) if constraints else 'aucune'}.",
            f"Materiel disponible: {', '.join(equipment) if equipment else 'aucun'}.",
            f"{len(exercises)} exercices selectionnes par groupe musculaire.",
        ],
        storage={
            "engine": "mongodb",
            "status": "connected" if mongo_ok else "disconnected",
        },
    )
