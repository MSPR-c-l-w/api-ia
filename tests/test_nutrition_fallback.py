import asyncio

from app.contexts.nutrition.application.use_cases.analyze_meal import AnalyzeMealUseCase
from app.contexts.nutrition.domain.models import VisionDetection
from app.contexts.nutrition.presentation.schemas import NutritionAnalysisRequest


class EmptyProvider:
    async def detect_foods(self, image_url: str | None, image_base64: str | None):
        return []


class FoodProvider:
    async def detect_foods(self, image_url: str | None, image_base64: str | None):
        return [VisionDetection(label="salade", confidence=0.91)]


class LowConfidenceProvider:
    async def detect_foods(self, image_url: str | None, image_base64: str | None):
        return [VisionDetection(label="salade", confidence=0.2)]


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


def test_analyze_meal_filters_low_confidence_detections():
    """Detections below 0.5 confidence are treated as no detection → stub fallback."""
    use_case = AnalyzeMealUseCase(vision_providers=[LowConfidenceProvider()])
    payload = NutritionAnalysisRequest(imageUrl="https://example.com/meal.jpg", userGoal="equilibre")

    result = asyncio.run(use_case.execute(payload))

    # Low-confidence detection is filtered out → falls back to stub
    assert result.model_status == "stub_ready_for_huggingface"


def test_analyze_meal_returns_imbalance_status_and_nutrient_details():
    use_case = AnalyzeMealUseCase(vision_providers=[FoodProvider()])
    payload = NutritionAnalysisRequest(imageUrl="https://example.com/meal.jpg", userGoal="perte_de_poids")

    result = asyncio.run(use_case.execute(payload))

    assert result.imbalance_status in ("EQUILIBRE", "DESEQUILIBRE")
    assert len(result.nutrient_details) > 0
    nutrient_names = {d.name for d in result.nutrient_details}
    assert "calories" in nutrient_names
    assert "proteins_g" in nutrient_names


def test_analyze_meal_feedback_list_not_empty():
    use_case = AnalyzeMealUseCase(vision_providers=[EmptyProvider()])
    payload = NutritionAnalysisRequest(imageUrl="https://example.com/meal.jpg", userGoal="prise_de_masse")

    result = asyncio.run(use_case.execute(payload))

    assert isinstance(result.feedback, list)
    assert len(result.feedback) > 0
