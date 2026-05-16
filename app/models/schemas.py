from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime


class NutritionAnalysisRequest(BaseModel):
    image_url: HttpUrl | None = None
    image_base64: str | None = None
    user_goal: str | None = None


class NutritionAnalysisResponse(BaseModel):
    detected_foods: list[dict]
    estimated_calories: int
    estimated_macros: dict
    feedback: list[str]
    model_status: str


class WorkoutProgramRequest(BaseModel):
    user_id: int = Field(alias="userId", ge=1)
    objectif: str = Field(min_length=1)
    niveau: str = Field(min_length=1)
    materiel: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class WorkoutSessionExerciseResponse(BaseModel):
    model_config = {"populate_by_name": True}

    id: str
    sets: int | None = None
    reps: int | None = None
    duree: int | None = None
    estimated_duration_minutes: int = Field(
        alias="estimatedDurationMinutes",
        description="Durée estimée de l'exercice en minutes",
    )


class WorkoutDayResponse(BaseModel):
    model_config = {"populate_by_name": True}

    jour: str
    is_rest_day: bool = Field(alias="isRestDay")
    estimated_session_minutes: int = Field(alias="estimatedSessionMinutes")
    exercices: list[WorkoutSessionExerciseResponse] = Field(default_factory=list)


class WorkoutProgramResponse(BaseModel):
    model_config = {"populate_by_name": True}

    program_id: str = Field(alias="programId")
    user_id: int = Field(alias="userId")
    statut: str
    programme: list[WorkoutDayResponse]
    generated_at: datetime = Field(alias="generatedAt")
