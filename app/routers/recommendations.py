from fastapi import APIRouter, Depends

from app.dependencies.api_key import verify_api_key
from app.models.schemas import (
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
)
from app.services.workout_feedback_service import submit_workout_feedback
from app.services.workout_program_service import create_workout_program

router = APIRouter(dependencies=[Depends(verify_api_key)])


@router.post(
    "/workout",
    response_model=WorkoutProgramResponse,
    summary="Générer un programme d'entraînement hebdomadaire",
    responses={
        400: {"description": "Données utilisateur insuffisantes"},
        401: {"description": "Clé API invalide ou absente"},
        503: {"description": "MongoDB indisponible"},
    },
)
async def generate_workout_program(
    payload: WorkoutProgramRequest,
) -> WorkoutProgramResponse:
    return await create_workout_program(payload)


@router.post(
    "/workout/{program_id}/feedback",
    response_model=WorkoutFeedbackResponse,
    summary="Soumettre un retour sur un programme généré",
    responses={
        404: {"description": "Programme introuvable"},
        401: {"description": "Clé API invalide ou absente"},
        422: {"description": "Validation du corps de requête échouée"},
        503: {"description": "MongoDB indisponible"},
    },
)
async def post_workout_feedback(
    program_id: str,
    payload: WorkoutFeedbackRequest,
) -> WorkoutFeedbackResponse:
    return await submit_workout_feedback(program_id, payload)
