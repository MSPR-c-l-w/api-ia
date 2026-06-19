from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class DetectedFood(BaseModel):
    label: str = Field(description="Nom de l'aliment détecté")
    confidence: float = Field(ge=0, le=1, description="Score de confiance du modèle")


class EstimatedMacros(BaseModel):
    proteins_g: float = Field(ge=0, description="Protéines estimées (g)")
    carbs_g: float = Field(ge=0, description="Glucides estimés (g)")
    fats_g: float = Field(ge=0, description="Lipides estimés (g)")
    fibers_g: float = Field(default=0.0, ge=0, description="Fibres estimées (g)")


class NutrientDetailSchema(BaseModel):
    """Statut d'un nutriment par rapport à la cible quotidienne (pour 1 repas)."""

    name: str = Field(description="Nom du nutriment")
    actual: float = Field(description="Valeur mesurée pour ce repas")
    target: float = Field(
        description="Cible pour ce repas (1/3 de la cible journalière)"
    )
    unit: str = Field(description="Unité (kcal ou g)")
    status: str = Field(description="OK | EXCES | DEFICIT")
    deviation_pct: float = Field(description="Écart par rapport à la cible en %")


class NutritionAnalysisRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "imageUrl": "https://example.com/meal.jpg",
                "userGoal": "perte_de_poids",
                "weightKg": 75.0,
                "heightCm": 175.0,
                "ageYears": 30,
                "gender": "male",
                "physicalActivityLevel": "moderately_active",
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
    # Biometric fields (from backend User + HealthProfile)
    weight_kg: float | None = Field(
        default=None,
        alias="weightKg",
        gt=0,
        le=500,
        description="Poids de l'utilisateur en kg (HealthProfile.weight)",
    )
    height_cm: float | None = Field(
        default=None,
        alias="heightCm",
        gt=0,
        le=300,
        description="Taille de l'utilisateur en cm (User.height)",
    )
    age_years: int | None = Field(
        default=None,
        alias="ageYears",
        ge=1,
        le=120,
        description="Âge de l'utilisateur en années (calculé depuis User.date_of_birth)",
    )
    gender: str | None = Field(
        default=None,
        description="Sexe : 'male' | 'female' (User.gender)",
        examples=["male", "female"],
    )
    physical_activity_level: str | None = Field(
        default=None,
        alias="physicalActivityLevel",
        description="Niveau d'activité physique (HealthProfile.physical_activity_level)",
        examples=[
            "sedentary",
            "lightly_active",
            "moderately_active",
            "very_active",
            "extra_active",
        ],
    )
    daily_calories_target: int | None = Field(
        default=None,
        alias="dailyCaloriesTarget",
        ge=800,
        le=6000,
        description="Objectif calorique quotidien (HealthProfile.daily_calories_target) — remplace le calcul TDEE si fourni",
    )


class NutritionAnalysisResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "detectedFoods": [{"label": "poulet", "confidence": 0.91}],
                "estimatedCalories": 520,
                "estimatedMacros": {
                    "proteins_g": 32,
                    "carbs_g": 54,
                    "fats_g": 14,
                    "fibers_g": 3.0,
                },
                "imbalanceStatus": "EQUILIBRE",
                "nutrientDetails": [],
                "feedback": ["Repas équilibré pour un objectif de perte de poids."],
                "modelStatus": "vision_stub",
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
    imbalance_status: str = Field(
        alias="imbalanceStatus",
        description="Statut global du repas : EQUILIBRE | DESEQUILIBRE",
        examples=["EQUILIBRE", "DESEQUILIBRE"],
    )
    nutrient_details: list[NutrientDetailSchema] = Field(
        default_factory=list,
        alias="nutrientDetails",
        description="Détail par nutriment avec statut et écart",
    )
    feedback: list[str] = Field(
        description="Conseils textuels générés pour l'utilisateur",
    )
    model_status: str = Field(
        alias="modelStatus",
        description="État du modèle IA (stub ou modèle actif)",
        examples=["vision_stub"],
    )


class PhotoDetectedFood(BaseModel):
    """Aliment reconnu sur la photo — format consommé par le backend NestJS."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="Nom de l'aliment reconnu (issu du catalogue)")
    quantity_g: float | None = Field(
        default=None,
        alias="quantityG",
        description="Quantité estimée pour cet aliment (g)",
    )
    confidence: float = Field(
        ge=0, le=1, description="Score de confiance de la détection"
    )


class PhotoMacros(BaseModel):
    """Macros agrégées du plat — format consommé par le backend NestJS."""

    model_config = ConfigDict(populate_by_name=True)

    calories: float = Field(description="Calories totales estimées (kcal)")
    protein_g: float = Field(alias="proteinG", description="Protéines (g)")
    carbs_g: float = Field(alias="carbsG", description="Glucides (g)")
    fat_g: float = Field(alias="fatG", description="Lipides (g)")


class PhotoAnalysisResponse(BaseModel):
    """Réponse de ``POST /ai/nutrition/analyze-photo``.

    Contrat strictement aligné sur ``FoodAnalysisResult`` du backend NestJS
    (``src/ai/interfaces/food-analysis.interface.ts``).
    """

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "imageUrl": "https://example.com/meal.jpg",
                "alimentsDetectes": [
                    {"name": "poulet", "quantityG": 150.0, "confidence": 0.91},
                    {"name": "riz", "quantityG": 150.0, "confidence": 0.88},
                ],
                "macros": {
                    "calories": 442,
                    "proteinG": 50.6,
                    "carbsG": 42.6,
                    "fatG": 5.9,
                },
                "suggestions": ["Repas équilibré pour un objectif d'équilibre."],
                "modelStatus": "vision_stub",
            },
        },
    )

    image_url: str = Field(alias="imageUrl", description="URL de la photo analysée")
    aliments_detectes: list[PhotoDetectedFood] = Field(
        alias="alimentsDetectes", description="Aliments reconnus dans le plat"
    )
    macros: PhotoMacros = Field(description="Macros estimées du plat")
    suggestions: list[str] = Field(description="Conseils nutritionnels générés")
    model_status: str = Field(
        alias="modelStatus", description="État du modèle de détection"
    )


class MealPlanRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": 42,
                "userGoal": "perte_de_poids",
                "dietaryConstraints": ["vegetarien"],
                "allergies": ["arachide"],
                "dailyCaloriesTarget": 1900,
                "weightKg": 70.0,
                "heightCm": 168.0,
                "ageYears": 28,
                "gender": "female",
                "physicalActivityLevel": "lightly_active",
            },
        },
    )

    user_id: int | None = Field(
        default=None,
        alias="userId",
        ge=1,
        description="Identifiant utilisateur (FK logique vers User.id NestJS) — si fourni, la recommandation est persistée en MongoDB",
        examples=[42],
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
        description="Objectif calorique quotidien (HealthProfile.daily_calories_target) — remplace le calcul TDEE si fourni",
    )
    # Biometric fields
    weight_kg: float | None = Field(
        default=None,
        alias="weightKg",
        gt=0,
        le=500,
        description="Poids en kg (HealthProfile.weight)",
    )
    height_cm: float | None = Field(
        default=None,
        alias="heightCm",
        gt=0,
        le=300,
        description="Taille en cm (User.height)",
    )
    age_years: int | None = Field(
        default=None,
        alias="ageYears",
        ge=1,
        le=120,
        description="Âge en années (calculé depuis User.date_of_birth)",
    )
    gender: str | None = Field(
        default=None,
        description="Sexe : 'male' | 'female' (User.gender)",
    )
    physical_activity_level: str | None = Field(
        default=None,
        alias="physicalActivityLevel",
        description="Niveau d'activité physique (HealthProfile.physical_activity_level)",
        examples=[
            "sedentary",
            "lightly_active",
            "moderately_active",
            "very_active",
            "extra_active",
        ],
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
