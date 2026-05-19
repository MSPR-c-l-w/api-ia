import asyncio

from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.infrastructure.vision.huggingface_provider import VisionDetection
from app.contexts.nutrition.presentation.schemas import NutritionAnalysisRequest


class EmptyProvider:
    async def detect_foods(self, image_url: str | None, image_base64: str | None):
        return []


class FoodProvider:
    async def detect_foods(self, image_url: str | None, image_base64: str | None):
        return [VisionDetection(label="salade", confidence=0.91)]


def test_analyze_meal_uses_google_fallback_when_primary_empty():
    use_case = AnalyzeMealUseCase(vision_providers=[EmptyProvider(), FoodProvider()])
    payload = NutritionAnalysisRequest(imageUrl="https://example.com/meal.jpg", userGoal="equilibre")

    result = asyncio.run(use_case.execute(payload))

    assert result.model_status == "google_vision_active"
    assert len(result.detected_foods) == 1
    assert result.detected_foods[0].label == "salade"


def test_analyze_meal_falls_back_to_stub_when_all_providers_empty():
    use_case = AnalyzeMealUseCase(vision_providers=[EmptyProvider(), EmptyProvider()])
    payload = NutritionAnalysisRequest(imageUrl="https://example.com/meal.jpg", userGoal="equilibre")

    result = asyncio.run(use_case.execute(payload))

    assert result.model_status == "stub_ready_for_huggingface"
    assert result.detected_foods[0].label == "poulet-riz"
