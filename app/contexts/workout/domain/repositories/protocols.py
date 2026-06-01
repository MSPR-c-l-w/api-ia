from typing import Any, Protocol

from app.contexts.workout.domain.entities.workout_program import (
    UserFitnessProfile,
    WorkoutFeedback,
    WorkoutProgram,
)


class WorkoutProgramRepository(Protocol):
    async def ensure_available(self) -> None:
        """Lève MongoUnavailableError si la base est inaccessible."""

    async def save(self, program: WorkoutProgram) -> str:
        """Persiste un programme et retourne son identifiant."""

    async def find_raw_by_id(self, program_id: str) -> dict[str, Any] | None:
        """Retourne le document brut ou None si introuvable."""

    async def get_recent_exercise_ids(
        self, user_id: int, *, weeks: int = 2
    ) -> list[str]:
        """IDs d'exercices utilisés récemment (rotation anti-répétition)."""


class WorkoutFeedbackRepository(Protocol):
    async def save(self, feedback: WorkoutFeedback) -> str:
        """Persiste un feedback et retourne son identifiant."""

    async def count_recent_trop_facile(
        self, user_id: int, *, window_days: int = 30
    ) -> int:
        """Nombre de signaux « trop facile » sur la fenêtre glissante."""


class FitnessProfileRepository(Protocol):
    async def find_by_user_id(self, user_id: int) -> UserFitnessProfile | None:
        """Charge le profil sportif ou None."""

    async def upsert(self, profile: UserFitnessProfile) -> None:
        """Crée ou met à jour le profil sportif."""
