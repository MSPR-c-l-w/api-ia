from functools import lru_cache

from app.config import settings
from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.application.use_cases.generate_meal_plan import (
    GenerateMealPlanUseCase,
)
from app.contexts.nutrition.infrastructure.vision.google_vision_provider import (
    GoogleVisionProvider,
)
from app.contexts.nutrition.infrastructure.vision.huggingface_provider import (
    HuggingFaceVisionProvider,
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

        hf_provider = HuggingFaceVisionProvider(
            endpoint=settings.nutrition_huggingface_endpoint,
            api_key=settings.nutrition_huggingface_api_key,
            timeout_seconds=settings.nutrition_provider_timeout_seconds,
        )
        google_provider = GoogleVisionProvider(
            endpoint=settings.nutrition_google_vision_endpoint,
            api_key=settings.nutrition_google_vision_api_key,
            timeout_seconds=settings.nutrition_provider_timeout_seconds,
        )
        self.analyze_meal = AnalyzeMealUseCase(
            vision_providers=[hf_provider, google_provider],
        )
        self.generate_meal_plan = GenerateMealPlanUseCase()


@lru_cache
def get_container() -> Container:
    return Container()
