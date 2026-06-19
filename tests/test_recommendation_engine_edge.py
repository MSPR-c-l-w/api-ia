"""Cas limites du moteur de recommandation (branches résiduelles)."""

from app.contexts.workout.domain.services.recommendation_engine import (
    _level_index,
    _score_objective,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring


def _profile(objectif="renforcement", niveau="debutant"):
    return UserProfileForScoring(
        objectif=objectif,
        niveau=niveau,
        materiel=[],
        preferences=[],
        limitations=[],
    )


def test_level_index_unknown_defaults_to_zero():
    assert _level_index("niveau-inexistant") == 0


def test_score_objective_without_objectives_is_neutral():
    exercise = ExerciseDefinition(
        id="x",
        name="X",
        muscle_group="jambes",
        level="debutant",
        objectives=[],
        equipment=[],
        contraindications=[],
        tags=[],
    )

    assert _score_objective(exercise, _profile()) == 0.5
