from fastapi import APIRouter, Depends

from app.dependencies.api_key import verify_api_key
from app.models.schemas import WorkoutProgramRequest, WorkoutProgramResponse
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
