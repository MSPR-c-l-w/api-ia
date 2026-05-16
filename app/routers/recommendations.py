from fastapi import APIRouter, Depends, Path

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
    description=(
        "Construit un programme sur 7 jours selon le profil utilisateur, "
        "avec rotation anti-répétition et persistance MongoDB."
    ),
    responses={
        400: {"description": "Données utilisateur insuffisantes (`INSUFFICIENT_USER_DATA`)"},
        401: {"description": "Clé API invalide ou absente (`INVALID_API_KEY`)"},
        503: {"description": "MongoDB indisponible (`MONGODB_UNAVAILABLE`)"},
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
    description=(
        "Enregistre le feedback, met à jour le profil sportif MongoDB "
        "(niveau, limitations temporaires 30 jours)."
    ),
    responses={
        404: {"description": "Programme introuvable (`PROGRAM_NOT_FOUND`)"},
        401: {"description": "Clé API invalide ou absente (`INVALID_API_KEY`)"},
        422: {"description": "Validation du corps de requête échouée"},
        503: {"description": "MongoDB indisponible (`MONGODB_UNAVAILABLE`)"},
    },
)
async def post_workout_feedback(
    payload: WorkoutFeedbackRequest,
    program_id: str = Path(
        ...,
        description="Identifiant MongoDB du programme (`_id` hex)",
        examples=["665a1b2c3d4e5f6789012345"],
    ),
) -> WorkoutFeedbackResponse:
    return await submit_workout_feedback(program_id, payload)
