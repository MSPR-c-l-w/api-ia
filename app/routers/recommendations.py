from flask import Blueprint

from app.composition.container import get_container
from app.contexts.workout.presentation.schemas import (
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
)
from app.dependencies.api_key import require_api_key
from app.presentation.exception_handlers import map_application_errors
from app.presentation.http import model_response, parse_json

recommendations_bp = Blueprint(
    "recommendations", __name__, url_prefix="/recommendations"
)


@recommendations_bp.post("/workout")
@require_api_key
@map_application_errors
async def generate_workout_program():
    """Génère un programme d'entraînement hebdomadaire personnalisé."""
    payload = parse_json(WorkoutProgramRequest)
    result: WorkoutProgramResponse = (
        await get_container().create_workout_program.execute(payload)
    )
    return model_response(result)


@recommendations_bp.get("/workout/<program_id>")
@require_api_key
@map_application_errors
async def get_workout_program(program_id: str):
    """Récupère un programme sportif depuis MongoDB via son ID."""
    result: WorkoutProgramResponse = (
        await get_container().get_workout_program.execute(program_id)
    )
    return model_response(result)


@recommendations_bp.post("/workout/<program_id>/feedback")
@require_api_key
@map_application_errors
async def post_workout_feedback(program_id: str):
    """Enregistre un retour utilisateur et ajuste le profil sportif."""
    payload = parse_json(WorkoutFeedbackRequest)
    result: WorkoutFeedbackResponse = (
        await get_container().submit_workout_feedback.execute(
            program_id,
            payload,
        )
    )
    return model_response(result)
