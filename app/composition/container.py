from functools import lru_cache
import logging

import httpx

from app.config import settings
from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.application.use_cases.generate_meal_plan import (
    GenerateMealPlanUseCase,
)
from app.contexts.nutrition.domain.services import NutritionImbalanceService
from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService
from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import (
    BackendNutritionLookupService,
)
from app.contexts.nutrition.infrastructure.cache import AiCacheService
from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider
from app.contexts.nutrition.infrastructure.nutrition_lookup import NutritionLookupService
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
            test_mode=settings.skip_mongodb_on_startup,
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
        llm_provider = LlmProvider(
            endpoint=settings.nutrition_llm_endpoint,
            api_key=settings.nutrition_llm_api_key,
            timeout_seconds=settings.nutrition_llm_timeout_seconds,
        )
        nutrition_lookup = NutritionLookupService()
        # Remplace par le lookup backend avec fallback sur la table statique
        _logger = logging.getLogger(__name__)
        try:
            _backend_auth = BackendAuthService(
                backend_url=settings.backend_url,
                email=settings.backend_service_email,
                password=settings.backend_service_password,
                timeout_seconds=settings.backend_timeout_seconds,
            )
            _token = _backend_auth.get_token()
            nutrition_lookup = BackendNutritionLookupService(
                backend_url=settings.backend_url,
                access_token=_token,
                timeout_seconds=settings.backend_timeout_seconds,
            )
            _logger.info(
                "Container: BackendNutritionLookupService actif (backend: %s)",
                settings.backend_url,
            )
        except (httpx.HTTPError, RuntimeError, OSError) as exc:
            _logger.warning(
                "Container: impossible de connecter le lookup nutrition au backend (%s)."
                " Fallback sur table statique.",
                exc,
            )
        imbalance_service = NutritionImbalanceService()
        tdee_calculator = TdeeCalculator()
        ai_cache = AiCacheService()

        self.analyze_meal = AnalyzeMealUseCase(
            vision_providers=[hf_provider, google_provider],
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
