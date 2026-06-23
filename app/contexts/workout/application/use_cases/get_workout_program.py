from app.contexts.workout.domain.repositories.protocols import WorkoutProgramRepository
from app.contexts.workout.presentation.schemas import (
    WorkoutDayResponse,
    WorkoutProgramResponse,
    WorkoutSessionExerciseResponse,
)
from app.shared.application.exceptions import ProgramNotFoundError


class GetWorkoutProgramUseCase:
    """Récupère un programme sportif depuis MongoDB via son ID."""

    def __init__(self, program_repository: WorkoutProgramRepository) -> None:
        self._programs = program_repository

    async def execute(self, program_id: str) -> WorkoutProgramResponse:
        doc = await self._programs.find_raw_by_id(program_id)
        if doc is None:
            raise ProgramNotFoundError()

        days = []
        for day in doc.get('programme', []):
            exercices = [
                WorkoutSessionExerciseResponse(
                    id=ex['id'],
                    name=ex.get('name'),
                    sets=ex.get('sets'),
                    reps=ex.get('reps'),
                    duree=ex.get('duree'),
                    estimatedDurationMinutes=ex.get('estimatedDurationMinutes', 10),
                )
                for ex in day.get('exercices', [])
            ]
            days.append(
                WorkoutDayResponse(
                    jour=day['jour'],
                    isRestDay=day.get('isRestDay', len(exercices) == 0),
                    estimatedSessionMinutes=day.get(
                        'estimatedSessionMinutes',
                        sum(e.estimated_duration_minutes for e in exercices),
                    ),
                    exercices=exercices,
                )
            )

        return WorkoutProgramResponse(
            programId=str(doc['_id']),
            userId=doc['userId'],
            statut=doc.get('statut', 'ACTIVE'),
            programme=days,
            generatedAt=doc['generatedAt'],
        )
