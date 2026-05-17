"""Compatibilité — délégué au use case ``SubmitWorkoutFeedbackUseCase``."""

from app.composition.container import get_container
from app.contexts.workout.presentation.schemas import (
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
)


async def submit_workout_feedback(
    program_id: str,
    payload: WorkoutFeedbackRequest,
) -> WorkoutFeedbackResponse:
    return await get_container().submit_workout_feedback.execute(program_id, payload)
