"""Compatibilité — délégué au use case ``CreateWorkoutProgramUseCase``."""

from app.composition.container import get_container
from app.contexts.workout.presentation.schemas import (
    WorkoutProgramRequest,
    WorkoutProgramResponse,
)


async def create_workout_program(
    payload: WorkoutProgramRequest,
) -> WorkoutProgramResponse:
    return await get_container().create_workout_program.execute(payload)
