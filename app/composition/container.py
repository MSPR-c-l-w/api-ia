from functools import lru_cache

from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.application.use_cases.generate_meal_plan import (
    GenerateMealPlanUseCase,
)
from app.contexts.workout.application.use_cases.create_workout_program import (
    CreateWorkoutProgramUseCase,
)
from app.contexts.workout.application.use_cases.submit_workout_feedback import (
    SubmitWorkoutFeedbackUseCase,
)
from app.contexts.workout.infrastructure.persistence import (
    MongoFitnessProfileRepository,
    MongoWorkoutFeedbackRepository,
    MongoWorkoutProgramRepository,
)


class Container:
    """Composition root — câblage des use cases et adaptateurs infrastructure."""

    def __init__(self) -> None:
        self._workout_programs = MongoWorkoutProgramRepository()
        self._workout_feedbacks = MongoWorkoutFeedbackRepository()
        self._fitness_profiles = MongoFitnessProfileRepository()

        self.create_workout_program = CreateWorkoutProgramUseCase(self._workout_programs)
        self.submit_workout_feedback = SubmitWorkoutFeedbackUseCase(
            self._workout_programs,
            self._workout_feedbacks,
            self._fitness_profiles,
        )
        self.analyze_meal = AnalyzeMealUseCase()
        self.generate_meal_plan = GenerateMealPlanUseCase()


@lru_cache
def get_container() -> Container:
    return Container()
