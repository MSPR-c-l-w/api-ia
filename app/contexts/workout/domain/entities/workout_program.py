from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class WorkoutProgramStatus(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class PlannedExercise(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(description="Identifiant exercice (référence catalogue)")
    sets: int | None = None
    reps: int | None = None
    duree: int | None = Field(
        default=None,
        description="Durée en minutes si applicable",
    )


class ProgramDay(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    jour: str = Field(description="Jour de la semaine, ex. lundi")
    exercices: list[PlannedExercise] = Field(default_factory=list)


class WorkoutProgram(BaseModel):
    """Entité programme — persistance MongoDB ``workout_programs``."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    programme: list[ProgramDay] = Field(default_factory=list)
    statut: WorkoutProgramStatus = WorkoutProgramStatus.ACTIVE
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        alias="generatedAt",
    )


class UserFitnessProfile(BaseModel):
    """Profil sportif utilisateur — collection ``user_fitness_profiles``."""

    model_config = ConfigDict(populate_by_name=True)

    user_id: int = Field(alias="userId")
    objectif: str
    niveau: str
    materiel: list[str] = Field(default_factory=list)
    preferences: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    historique: list[dict] = Field(default_factory=list)


class WorkoutFeedback(BaseModel):
    """Retour utilisateur — collection ``workout_feedbacks``."""

    model_config = ConfigDict(populate_by_name=True)

    program_id: str = Field(alias="programId")
    user_id: int = Field(alias="userId")
    rating: int = Field(ge=1, le=5)
    trop_difficile: bool = Field(default=False, alias="tropDifficile")
    trop_facile: bool = Field(default=False, alias="tropFacile")
    exercices_problematiques: list[str] = Field(
        default_factory=list,
        alias="exercicesProblematiques",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        alias="createdAt",
    )
