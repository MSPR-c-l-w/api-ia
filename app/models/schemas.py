from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class HealthResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "timestamp": "2026-05-16T12:00:00Z",
            },
        },
    )

    status: str = Field(
        description="État du service",
        examples=["ok"],
    )
    timestamp: datetime = Field(
        description="Horodatage UTC de la sonde",
        examples=["2026-05-16T12:00:00Z"],
    )


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


class WorkoutProgramRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "userId": 42,
                "objectif": "renforcement",
                "niveau": "debutant",
                "materiel": ["tapis", "haltères"],
                "preferences": ["faible impact"],
                "limitations": ["mal au genou"],
            },
        },
    )

    user_id: int = Field(
        alias="userId",
        ge=1,
        description="Identifiant utilisateur (FK logique vers User.id NestJS)",
        examples=[42],
    )
    objectif: str = Field(
        min_length=1,
        description="Objectif sportif principal",
        examples=["renforcement", "perte_de_poids", "endurance"],
    )
    niveau: str = Field(
        min_length=1,
        description="Niveau de forme (`debutant`, `intermediaire`, `avance`, `athlete`)",
        examples=["debutant"],
    )
    materiel: list[str] = Field(
        default_factory=list,
        description="Équipement disponible",
        examples=[["tapis", "haltères"]],
    )
    preferences: list[str] = Field(
        default_factory=list,
        description="Préférences d'entraînement (tags)",
        examples=[["faible impact", "cardio"]],
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Blessures ou contraintes à respecter",
        examples=[["mal au genou"]],
    )


class WorkoutSessionExerciseResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Identifiant exercice (catalogue interne)", examples=["pont-fessier"])
    sets: int | None = Field(default=None, description="Nombre de séries", examples=[3])
    reps: int | None = Field(default=None, description="Répétitions par série", examples=[12])
    duree: int | None = Field(
        default=None,
        description="Durée en minutes si applicable",
        examples=[15],
    )
    estimated_duration_minutes: int = Field(
        alias="estimatedDurationMinutes",
        description="Durée estimée de l'exercice en minutes",
        examples=[10],
    )


class WorkoutDayResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jour: str = Field(description="Jour de la semaine", examples=["lundi"])
    is_rest_day: bool = Field(alias="isRestDay", description="Jour de repos", examples=[False])
    estimated_session_minutes: int = Field(
        alias="estimatedSessionMinutes",
        description="Durée totale estimée de la séance (minutes)",
        examples=[45],
    )
    exercices: list[WorkoutSessionExerciseResponse] = Field(
        default_factory=list,
        description="Exercices planifiés pour la journée",
    )


class WorkoutFeedbackRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "rating": 4,
                "tropDifficile": False,
                "tropFacile": False,
                "exercicesProblematiques": ["squat-pdc"],
            },
        },
    )

    rating: int = Field(ge=1, le=5, description="Note globale du programme (1–5)", examples=[4])
    trop_difficile: bool = Field(
        default=False,
        alias="tropDifficile",
        description="Le programme était trop difficile",
        examples=[False],
    )
    trop_facile: bool = Field(
        default=False,
        alias="tropFacile",
        description="Le programme était trop facile",
        examples=[False],
    )
    exercices_problematiques: list[str] = Field(
        default_factory=list,
        alias="exercicesProblematiques",
        description="IDs d'exercices à éviter temporairement (30 jours)",
        examples=[["squat-pdc"]],
    )


class WorkoutFeedbackResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    feedback_id: str = Field(alias="feedbackId", description="Identifiant MongoDB du feedback")
    program_id: str = Field(alias="programId", description="Programme concerné")
    user_id: int = Field(alias="userId", description="Utilisateur", examples=[42])
    profile_niveau: str = Field(
        alias="profileNiveau",
        description="Niveau sportif après ajustement éventuel",
        examples=["intermediaire"],
    )
    created_at: datetime = Field(alias="createdAt", description="Horodatage du feedback")


class WorkoutProgramResponse(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "programId": "665a1b2c3d4e5f6789012345",
                "userId": 42,
                "statut": "ACTIVE",
                "programme": [],
                "generatedAt": "2026-05-16T12:00:00Z",
            },
        },
    )

    program_id: str = Field(
        alias="programId",
        description="Identifiant MongoDB du programme (référencé par le backend SQL)",
    )
    user_id: int = Field(alias="userId", description="Utilisateur", examples=[42])
    statut: str = Field(description="Statut du programme", examples=["ACTIVE", "ARCHIVED"])
    programme: list[WorkoutDayResponse] = Field(description="Planning sur 7 jours")
    generated_at: datetime = Field(alias="generatedAt", description="Date de génération")
