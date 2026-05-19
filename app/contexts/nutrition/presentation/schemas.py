from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DetectedFood(BaseModel):
    label: str = Field(description="Nom de l'aliment détecté")
    confidence: float = Field(ge=0, le=1, description="Score de confiance du modèle")


class EstimatedMacros(BaseModel):
    proteins_g: float = Field(ge=0, description="Protéines estimées (g)")
    carbs_g: float = Field(ge=0, description="Glucides estimés (g)")
    fats_g: float = Field(ge=0, description="Lipides estimés (g)")


class NutritionAnalysisRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
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
        populate_by_name=True,
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

    detected_foods: list[DetectedFood] = Field(
        alias="detectedFoods",
        description="Aliments détectés avec scores de confiance",
    )
    estimated_calories: int = Field(
        alias="estimatedCalories",
        description="Estimation calorique totale (kcal)",
        examples=[520],
    )
    estimated_macros: EstimatedMacros = Field(
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


class MealPlanRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userGoal": "perte_de_poids",
                "dietaryConstraints": ["vegetarien"],
                "allergies": ["arachide"],
                "dailyCaloriesTarget": 1900,
            },
        },
    )

    user_goal: str = Field(
        alias="userGoal",
        description="Objectif nutritionnel de l'utilisateur",
        examples=["perte_de_poids", "prise_de_masse", "equilibre"],
    )
    dietary_constraints: list[str] = Field(
        default_factory=list,
        alias="dietaryConstraints",
        description="Contraintes alimentaires déclarées",
    )
    allergies: list[str] = Field(
        default_factory=list,
        description="Allergies à exclure des propositions",
    )
    daily_calories_target: int | None = Field(
        default=None,
        ge=800,
        le=5000,
        alias="dailyCaloriesTarget",
        description="Objectif calorique quotidien",
    )


class DailyMealPlan(BaseModel):
    day: int = Field(ge=1, le=7, description="Jour du plan (1 à 7)")
    breakfast: str = Field(description="Petit-déjeuner")
    lunch: str = Field(description="Déjeuner")
    dinner: str = Field(description="Dîner")
    snack: str | None = Field(default=None, description="Collation optionnelle")
    estimated_calories: int = Field(
        ge=0,
        alias="estimatedCalories",
        description="Calories estimées sur la journée",
    )


class MealPlanResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userGoal": "perte_de_poids",
                "days": [
                    {
                        "day": 1,
                        "breakfast": "Skyr + fruits rouges + flocons d'avoine",
                        "lunch": "Salade quinoa, pois chiches, légumes croquants",
                        "dinner": "Saumon, brocoli vapeur, patate douce",
                        "snack": "Une pomme",
                        "estimatedCalories": 1870,
                    }
                ],
                "notes": [
                    "Plan généré en mode stub local.",
                    "Exclut les allergènes déclarés.",
                ],
                "modelStatus": "stub_ready_for_llm",
            },
        },
    )

    user_goal: str = Field(alias="userGoal", description="Objectif utilisateur utilisé")
    days: list[DailyMealPlan] = Field(description="Plan repas sur 7 jours")
    notes: list[str] = Field(description="Informations complémentaires")
    model_status: str = Field(
        alias="modelStatus",
        description="État du moteur de génération",
        examples=["stub_ready_for_llm"],
    )
