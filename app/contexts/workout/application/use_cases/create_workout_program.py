from datetime import UTC, datetime

from app.contexts.workout.domain.entities.workout_program import (
    PlannedExercise,
    ProgramDay,
    WorkoutProgram,
    WorkoutProgramStatus,
)
from app.contexts.workout.domain.repositories.protocols import WorkoutProgramRepository
from app.contexts.workout.domain.services.weekly_planner import (
    _session_duration_bounds,
    generate_weekly_program,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring
from app.contexts.workout.presentation.schemas import (
    WorkoutDayResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
    WorkoutSessionExerciseResponse,
)
from app.shared.application.exceptions import InsufficientUserDataError


class CreateWorkoutProgramUseCase:
    """Use case : générer et persister un programme hebdomadaire personnalisé."""

    def __init__(
        self,
        program_repository: WorkoutProgramRepository,
        exercise_lookup: object | None = None,
    ) -> None:
        self._programs = program_repository
        self._exercise_lookup = exercise_lookup

    def _validate_profile(
        self, payload: WorkoutProgramRequest
    ) -> UserProfileForScoring:
        if not payload.objectif.strip() or not payload.niveau.strip():
            raise InsufficientUserDataError()
        return UserProfileForScoring(
            objectif=payload.objectif.strip(),
            niveau=payload.niveau.strip(),
            materiel=payload.materiel,
            preferences=payload.preferences,
            limitations=payload.limitations,
        )

    @staticmethod
    def _estimate_exercise_minutes(planned: PlannedExercise) -> int:
        if planned.duree is not None:
            return planned.duree
        if planned.sets and planned.reps:
            return max(5, planned.sets * 2)
        return 10

    def _build_response(
        self,
        program_id: str,
        user_id: int,
        niveau: str,
        programme_days: list[ProgramDay],
    ) -> WorkoutProgramResponse:
        min_dur, max_dur = _session_duration_bounds(niveau)
        default_session = (min_dur + max_dur) // 2

        days: list[WorkoutDayResponse] = []
        for day in programme_days:
            exercises = [
                WorkoutSessionExerciseResponse(
                    id=planned.id,
                    name=planned.name,
                    sets=planned.sets,
                    reps=planned.reps,
                    duree=planned.duree,
                    estimated_duration_minutes=self._estimate_exercise_minutes(planned),
                )
                for planned in day.exercices
            ]
            if exercises:
                session_minutes = sum(ex.estimated_duration_minutes for ex in exercises)
                session_minutes = max(session_minutes, default_session // 2)
            else:
                session_minutes = 0

            days.append(
                WorkoutDayResponse(
                    jour=day.jour,
                    is_rest_day=len(exercises) == 0,
                    estimated_session_minutes=session_minutes,
                    exercices=exercises,
                ),
            )

        return WorkoutProgramResponse(
            program_id=program_id,
            user_id=user_id,
            statut=WorkoutProgramStatus.ACTIVE.value,
            programme=days,
            generated_at=datetime.now(UTC),
        )

    async def execute(self, payload: WorkoutProgramRequest) -> WorkoutProgramResponse:
        profile = self._validate_profile(payload)
        await self._programs.ensure_available()

        recent_ids = await self._programs.get_recent_exercise_ids(payload.user_id)

        catalog = None
        if self._exercise_lookup is not None:
            try:
                catalog = await self._exercise_lookup.get_catalog()
            except Exception:
                catalog = None

        programme = generate_weekly_program(
            profile, recent_exercise_ids=recent_ids, catalog=catalog
        )

        if not any(day.exercices for day in programme):
            raise InsufficientUserDataError()

        program_doc = WorkoutProgram(
            user_id=payload.user_id,
            programme=programme,
            statut=WorkoutProgramStatus.ACTIVE,
        )
        program_id = await self._programs.save(program_doc)

        return self._build_response(
            program_id,
            payload.user_id,
            profile.niveau,
            programme,
        )
