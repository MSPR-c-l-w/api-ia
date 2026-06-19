"""Tests unitaires du use case CreateWorkoutProgram (branches résiduelles)."""

from unittest.mock import patch

import pytest

from app.contexts.workout.application.use_cases import create_workout_program as ucmod
from app.contexts.workout.application.use_cases.create_workout_program import (
    CreateWorkoutProgramUseCase,
)
from app.contexts.workout.domain.entities.workout_program import (
    PlannedExercise,
    ProgramDay,
)
from app.contexts.workout.presentation.schemas import WorkoutProgramRequest
from app.shared.application.exceptions import InsufficientUserDataError


class FakeProgramRepo:
    async def ensure_available(self) -> None:
        return None

    async def get_recent_exercise_ids(self, user_id: int, *, weeks: int = 2):
        return []

    async def save(self, program) -> str:
        return "prog-1"


def _payload(objectif="renforcement", niveau="debutant"):
    return WorkoutProgramRequest(userId=1, objectif=objectif, niveau=niveau)


def test_estimate_exercise_minutes_default():
    # Ni durée ni séries/reps → valeur par défaut de 10 minutes.
    assert (
        CreateWorkoutProgramUseCase._estimate_exercise_minutes(PlannedExercise(id="x"))
        == 10
    )


def test_estimate_exercise_minutes_from_duree():
    assert (
        CreateWorkoutProgramUseCase._estimate_exercise_minutes(
            PlannedExercise(id="x", duree=20)
        )
        == 20
    )


def test_estimate_exercise_minutes_from_sets_reps():
    assert (
        CreateWorkoutProgramUseCase._estimate_exercise_minutes(
            PlannedExercise(id="x", sets=4, reps=10)
        )
        == 8
    )


async def test_blank_objective_raises():
    use_case = CreateWorkoutProgramUseCase(FakeProgramRepo())

    with pytest.raises(InsufficientUserDataError):
        await use_case.execute(_payload(objectif="   "))


async def test_empty_program_raises():
    use_case = CreateWorkoutProgramUseCase(FakeProgramRepo())

    # Force un planning sans aucun exercice → données insuffisantes.
    with (
        patch.object(
            ucmod,
            "generate_weekly_program",
            return_value=[ProgramDay(jour="lundi", exercices=[])],
        ),
        pytest.raises(InsufficientUserDataError),
    ):
        await use_case.execute(_payload())


async def test_happy_path_builds_response():
    use_case = CreateWorkoutProgramUseCase(FakeProgramRepo())

    result = await use_case.execute(_payload())

    assert result.program_id == "prog-1"
    assert result.user_id == 1
    assert len(result.programme) == 7
