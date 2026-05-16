from fastapi import APIRouter

from app.models.schemas import RecommendationRequest, RecommendationResponse
from app.models.user_profile_scoring import UserProfileForScoring
from app.services import database
from app.services.recommendation_engine import recommend_exercises
from app.services.weekly_planner import generate_weekly_program

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
    weekly_programme = generate_weekly_program(profile)
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
            f"Programme hebdomadaire : {len([d for d in weekly_programme if d.exercices])} seances / 7 jours.",
        ],
        storage={
            "engine": "mongodb",
            "status": "connected" if mongo_ok else "disconnected",
            "weekly_programme": [day.model_dump() for day in weekly_programme],
        },
    )
