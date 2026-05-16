from pydantic import BaseModel, Field


class UserProfileForScoring(BaseModel):
    """Profil utilisateur pour le moteur multi-critères (#95)."""

    objectif: str
    niveau: str
    materiel: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
