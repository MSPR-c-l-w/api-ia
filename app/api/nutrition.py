from flask.views import MethodView
from flask_smorest import Blueprint

from app.schemas import NutritionAnalysisRequestSchema, NutritionAnalysisResponseSchema

blp = Blueprint(
    "nutrition",
    __name__,
    url_prefix="/api/nutrition",
    description="Food vision and nutrition analysis",
)


@blp.route("/analyze")
class NutritionAnalysisResource(MethodView):
    @blp.arguments(NutritionAnalysisRequestSchema)
    @blp.response(200, NutritionAnalysisResponseSchema)
    def post(self, payload):
        goal = payload.get("user_goal") or "equilibre"

        return {
            "detected_foods": [
                {
                    "label": "poulet-riz",
                    "confidence": 0.84,
                }
            ],
            "estimated_calories": 520,
            "estimated_macros": {
                "proteins_g": 32,
                "carbs_g": 54,
                "fats_g": 14,
            },
            "feedback": [
                f"Repas compatible avec un objectif de {goal}.",
                "Ajouter une source de fibres peut ameliorer l'equilibre nutritionnel.",
            ],
            "model_status": "stub_ready_for_huggingface",
        }
