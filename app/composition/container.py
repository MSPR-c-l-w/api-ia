import logging
from functools import lru_cache

import httpx

from app.config import settings
from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.application.use_cases.generate_meal_plan import (
    GenerateMealPlanUseCase,
)
from app.contexts.nutrition.domain.services import NutritionImbalanceService
from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService
from app.contexts.nutrition.infrastructure.cache import AiCacheService
from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider
from app.contexts.nutrition.infrastructure.mongo_nutrition_lookup import (
    MongoNutritionLookupService,
)
from app.contexts.nutrition.infrastructure.vision.google_vision_provider import (
    GoogleVisionProvider,
)
from app.contexts.workout.application.use_cases.create_workout_program import (
    CreateWorkoutProgramUseCase,
)
from app.contexts.workout.application.use_cases.submit_workout_feedback import (
    SubmitWorkoutFeedbackUseCase,
)
from app.contexts.workout.infrastructure.backend_exercise_lookup import (
    BackendExerciseLookupService,
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

        _exercise_lookup = None
        try:
            _backend_auth_ex = BackendAuthService(
                backend_url=settings.backend_url,
                email=settings.backend_service_email,
                password=settings.backend_service_password,
                timeout_seconds=settings.backend_timeout_seconds,
            )
            _exercise_token = _backend_auth_ex.get_token()
            _exercise_lookup = BackendExerciseLookupService(
                backend_url=settings.backend_url,
                access_token=_exercise_token,
                timeout_seconds=settings.backend_timeout_seconds,
            )
            logging.getLogger(__name__).info(
                "Container: BackendExerciseLookupService actif (backend: %s)",
                settings.backend_url,
            )
        except (httpx.HTTPError, RuntimeError, OSError) as exc:
            logging.getLogger(__name__).warning(
                "Container: impossible de connecter le lookup exercices au backend (%s)."
                " Fallback sur catalogue statique.",
                exc,
            )

        self.create_workout_program = CreateWorkoutProgramUseCase(
            self._workout_programs,
            exercise_lookup=_exercise_lookup,
        )
        self.submit_workout_feedback = SubmitWorkoutFeedbackUseCase(
            self._workout_programs,
            self._workout_feedbacks,
            self._fitness_profiles,
            test_mode=settings.skip_mongodb_on_startup,
        )

        google_provider = GoogleVisionProvider(
            endpoint=settings.nutrition_google_vision_endpoint,
            api_key=settings.nutrition_google_vision_api_key,
            timeout_seconds=settings.nutrition_provider_timeout_seconds,
        )
        llm_provider = LlmProvider(
            endpoint=settings.nutrition_llm_endpoint,
            api_key=settings.nutrition_llm_api_key,
            timeout_seconds=settings.nutrition_llm_timeout_seconds,
        )
        # Catalogue d'aliments servi depuis MongoDB (collection nutrition_foods),
        # avec fallback automatique sur la table statique embarquée.
        nutrition_lookup = MongoNutritionLookupService()
        logging.getLogger(__name__).info(
            "Container: MongoNutritionLookupService actif (collection nutrition_foods)"
        )
        imbalance_service = NutritionImbalanceService()
        tdee_calculator = TdeeCalculator()
        ai_cache = AiCacheService()

        self.analyze_meal = AnalyzeMealUseCase(
            vision_providers=[google_provider],
            nutrition_lookup=nutrition_lookup,
            imbalance_service=imbalance_service,
            llm_provider=llm_provider,
            cache=ai_cache,
            tdee_calculator=tdee_calculator,
        )
        self.generate_meal_plan = GenerateMealPlanUseCase(
            llm_provider=llm_provider,
            tdee_calculator=tdee_calculator,
            nutrition_lookup=nutrition_lookup,
        )


@lru_cache
def get_container() -> Container:
    return Container()
