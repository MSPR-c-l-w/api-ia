from app.contexts.nutrition.domain.models import VisionDetection
from app.contexts.nutrition.domain.ports import (
    CachePort,
    LlmProviderPort,
    NutritionLookupPort,
    VisionProviderPort,
)
from app.contexts.nutrition.domain.services import NutritionImbalanceService
from app.contexts.nutrition.domain.tdee import TdeeCalculator
from app.contexts.nutrition.presentation.schemas import (
    DetectedFood,
    EstimatedMacros,
    NutrientDetailSchema,
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)

_CONFIDENCE_THRESHOLD = 0.5


class AnalyzeMealUseCase:
    """
    Orchestrates a full meal analysis:
      1. Vision detection (Google Vision) with caching (#91)
      2. Confidence-threshold + non-food filtering (#85)
      3. Macro computation via embedded nutrition table (#86)
      4. Nutritional imbalance detection with personalised TDEE targets when
         biometrics are provided (#88)
      5. Personalised suggestions via LLM (with static fallback) (#89)
    """

    def __init__(
        self,
        vision_providers: list[VisionProviderPort],
        nutrition_lookup: NutritionLookupPort | None = None,
        imbalance_service: NutritionImbalanceService | None = None,
        llm_provider: LlmProviderPort | None = None,
        cache: CachePort | None = None,
        tdee_calculator: TdeeCalculator | None = None,
    ) -> None:
        from app.contexts.nutrition.infrastructure.cache import AiCacheService
        from app.contexts.nutrition.infrastructure.llm_provider import LlmProvider
        from app.contexts.nutrition.infrastructure.nutrition_lookup import (
            NutritionLookupService,
        )

        self._vision_providers = vision_providers
        self._nutrition_lookup = nutrition_lookup or NutritionLookupService()
        self._imbalance_service = imbalance_service or NutritionImbalanceService()
        self._llm_provider = llm_provider or LlmProvider(endpoint=None, api_key=None)
        self._cache = cache or AiCacheService()
        self._tdee_calculator = tdee_calculator or TdeeCalculator()

    async def execute(
        self, payload: NutritionAnalysisRequest
    ) -> NutritionAnalysisResponse:
        goal = payload.user_goal or "equilibre"
        image_url = str(payload.image_url) if payload.image_url else None

        # 1. Vision detection (with cache, TTL 1 h)
        cache_key = self._cache.image_key(image_url, payload.image_base64)
        cached_detections: list[VisionDetection] | None = self._cache.get(cache_key)

        provider_status = "stub"
        detections: list[VisionDetection] = []

        if cached_detections is not None:
            detections = cached_detections
            provider_status = "cached"
        else:
            for provider in self._vision_providers:
                provider_result = await provider.detect_foods(
                    image_url=image_url,
                    image_base64=payload.image_base64,
                )
                if provider_result:
                    detections = provider_result
                    provider_name = getattr(provider, "name", "")
                    if not provider_name:
                        class_name = provider.__class__.__name__
                        provider_name_chars: list[str] = []
                        for index, char in enumerate(class_name):
                            if char.isupper() and index > 0:
                                provider_name_chars.append("_")
                            provider_name_chars.append(char.lower())
                        provider_name = "".join(provider_name_chars)
                        if provider_name.endswith("_provider"):
                            provider_name = provider_name[: -len("_provider")]
                    provider_status = provider_name
                    # Only cache successful results
                    self._cache.set(cache_key, detections, ttl_seconds=3600)
                    break
            # If all providers failed, don't cache empty results (fail-open pattern)

        # 2. Confidence filtering + non-food filtering (#85)
        filtered = [
            d
            for d in detections
            if d.confidence >= _CONFIDENCE_THRESHOLD
            and self._nutrition_lookup.is_food_label(d.label)
        ]

        if filtered:
            detected_foods = [
                DetectedFood(label=item.label, confidence=item.confidence)
                for item in filtered
            ]
            model_status = f"{provider_status}_active"
        else:
            detected_foods = [DetectedFood(label="poulet-riz", confidence=0.84)]
            model_status = "vision_stub"

        # 3. Macro computation (#86)
        food_labels = [f.label for f in detected_foods]
        macros = await self._nutrition_lookup.compute_macros(food_labels)

        # 4. Build personalised health profile from biometrics (#88)
        health_profile = self._resolve_health_profile(payload, goal)

        # 5. Imbalance detection (#88)
        nutrient_details, meal_status = self._imbalance_service.detect_imbalances(
            macros=macros, health_profile=health_profile
        )

        # Build imbalance tokens for LLM prompt and cache key
        imbalance_tokens = [
            f"{d.name}_{d.status.value}"
            for d in nutrient_details
            if d.status.value != "OK"
        ]

        # 6. LLM suggestions (with cache, TTL 24 h) (#89)
        llm_cache_key = self._cache.llm_key(goal, imbalance_tokens)
        feedback: list[str] | None = self._cache.get(llm_cache_key)
        if feedback is None:
            feedback = await self._llm_provider.generate_suggestions(
                goal=goal,
                imbalance_tokens=imbalance_tokens,
            )
            self._cache.set(llm_cache_key, feedback, ttl_seconds=86400)

        return NutritionAnalysisResponse(
            detected_foods=detected_foods,
            estimated_calories=int(macros.calories),
            estimated_macros=EstimatedMacros(
                proteins_g=macros.proteins_g,
                carbs_g=macros.carbs_g,
                fats_g=macros.fats_g,
                fibers_g=macros.fibers_g,
            ),
            imbalance_status=meal_status.value,
            nutrient_details=[
                NutrientDetailSchema(
                    name=d.name,
                    actual=d.actual,
                    target=d.target,
                    unit=d.unit,
                    status=d.status.value,
                    deviation_pct=d.deviation_pct,
                )
                for d in nutrient_details
            ],
            feedback=feedback,
            model_status=model_status,
        )

    def _resolve_health_profile(self, payload: NutritionAnalysisRequest, goal: str):
        return self._tdee_calculator.resolve_health_profile(
            goal=goal,
            weight_kg=payload.weight_kg,
            height_cm=payload.height_cm,
            age_years=payload.age_years,
            gender=payload.gender,
            physical_activity_level=payload.physical_activity_level
            or "moderately_active",
            daily_calories_target=payload.daily_calories_target,
        )
