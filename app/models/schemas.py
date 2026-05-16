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


class RecommendationRequest(BaseModel):
    objective: str
    level: str
    constraints: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    duration_minutes: int = 30


class RecommendationResponse(BaseModel):
    session_name: str
    exercises: list[dict]
    rationale: list[str]
    storage: dict
