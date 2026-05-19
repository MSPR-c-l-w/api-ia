"""Compatibilité — entités déplacées dans le contexte workout."""

from app.contexts.workout.domain.entities.workout_program import (
    PlannedExercise,
    ProgramDay,
    UserFitnessProfile,
    WorkoutFeedback,
    WorkoutProgram,
    WorkoutProgramStatus,
)

__all__ = [
    "PlannedExercise",
    "ProgramDay",
    "UserFitnessProfile",
    "WorkoutFeedback",
    "WorkoutProgram",
    "WorkoutProgramStatus",
]
