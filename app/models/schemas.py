"""Réexport des DTOs API (couche présentation des contextes)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.contexts.nutrition.presentation.schemas import (
    NutritionAnalysisRequest,
    NutritionAnalysisResponse,
)
from app.contexts.workout.presentation.schemas import (
    WorkoutDayResponse,
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
    WorkoutProgramRequest,
    WorkoutProgramResponse,
    WorkoutSessionExerciseResponse,
)


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


__all__ = [
    "HealthResponse",
    "NutritionAnalysisRequest",
    "NutritionAnalysisResponse",
    "WorkoutDayResponse",
    "WorkoutFeedbackRequest",
    "WorkoutFeedbackResponse",
    "WorkoutProgramRequest",
    "WorkoutProgramResponse",
    "WorkoutSessionExerciseResponse",
]
