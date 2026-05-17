from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class NutritionAnalysisRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "imageUrl": "https://example.com/meal.jpg",
                "userGoal": "perte_de_poids",
            },
        },
    )

    image_url: HttpUrl | None = Field(
        default=None,
        alias="imageUrl",
        description="URL publique de la photo du repas",
        examples=["https://example.com/meal.jpg"],
    )
    image_base64: str | None = Field(
        default=None,
        alias="imageBase64",
        description="Image encodée en base64 (alternative à imageUrl)",
    )
    user_goal: str | None = Field(
        default=None,
        alias="userGoal",
        description="Objectif nutritionnel de l'utilisateur",
        examples=["perte_de_poids", "prise_de_masse", "equilibre"],
    )


class NutritionAnalysisResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detectedFoods": [{"label": "poulet-riz", "confidence": 0.84}],
                "estimatedCalories": 520,
                "estimatedMacros": {
                    "proteins_g": 32,
                    "carbs_g": 54,
                    "fats_g": 14,
                },
                "feedback": ["Repas équilibré pour un objectif de perte de poids."],
                "modelStatus": "stub_ready_for_huggingface",
            },
        },
    )

    detected_foods: list[dict] = Field(
        alias="detectedFoods",
        description="Aliments détectés avec scores de confiance",
    )
    estimated_calories: int = Field(
        alias="estimatedCalories",
        description="Estimation calorique totale (kcal)",
        examples=[520],
    )
    estimated_macros: dict = Field(
        alias="estimatedMacros",
        description="Macronutriments estimés (g)",
    )
    feedback: list[str] = Field(
        description="Conseils textuels générés pour l'utilisateur",
    )
    model_status: str = Field(
        alias="modelStatus",
        description="État du modèle IA (stub ou modèle actif)",
        examples=["stub_ready_for_huggingface"],
    )
