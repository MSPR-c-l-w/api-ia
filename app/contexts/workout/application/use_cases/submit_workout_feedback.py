from datetime import UTC, datetime, timedelta

from app.contexts.workout.domain.data.exercises_catalog import LEVEL_ORDER
from app.contexts.workout.domain.entities.workout_program import (
    UserFitnessProfile,
    WorkoutFeedback,
)
from app.contexts.workout.domain.repositories.protocols import (
    FitnessProfileRepository,
    WorkoutFeedbackRepository,
    WorkoutProgramRepository,
)
from app.contexts.workout.domain.services.recommendation_engine import _level_index
from app.contexts.workout.presentation.schemas import (
    WorkoutFeedbackRequest,
    WorkoutFeedbackResponse,
)
from app.shared.application.exceptions import (
    MongoUnavailableError,
    ProgramNotFoundError,
)
from app.shared.infrastructure import database

TEMP_LIMITATION_PREFIX = "exercice_problematique:"
TEMP_LIMITATION_DAYS = 30
REPEATED_TOO_EASY_WINDOW_DAYS = 30


def _bump_niveau(current: str) -> str:
    idx = _level_index(current)
    if idx < len(LEVEL_ORDER) - 1:
        return LEVEL_ORDER[idx + 1]
    return current


def _prune_expired_limitations(
    limitations: list[str],
    historique: list[dict],
) -> list[str]:
    now = datetime.now(UTC)
    active_exercise_ids: set[str] = set()
    for event in historique:
        if event.get("type") != "temporary_limitation":
            continue
        expires_raw = event.get("expiresAt")
        if not expires_raw:
            continue
        expires_at = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at > now:
            active_exercise_ids.update(event.get("exerciseIds", []))

    kept: list[str] = []
    for limitation in limitations:
        if limitation.startswith(TEMP_LIMITATION_PREFIX):
            exercise_id = limitation.removeprefix(TEMP_LIMITATION_PREFIX)
            if exercise_id in active_exercise_ids:
                kept.append(limitation)
        else:
            kept.append(limitation)
    return kept


def _merge_temporary_limitations(
    limitations: list[str],
    exercise_ids: list[str],
    historique: list[dict],
) -> tuple[list[str], list[dict]]:
    if not exercise_ids:
        return limitations, historique

    expires_at = datetime.now(UTC) + timedelta(days=TEMP_LIMITATION_DAYS)
    updated = list(limitations)
    for exercise_id in exercise_ids:
        token = f"{TEMP_LIMITATION_PREFIX}{exercise_id}"
        if token not in updated:
            updated.append(token)

    historique.append(
        {
            "type": "temporary_limitation",
            "exerciseIds": exercise_ids,
            "expiresAt": expires_at.isoformat(),
        },
    )
    return updated, historique


class SubmitWorkoutFeedbackUseCase:
    """Use case : enregistrer un retour utilisateur et ajuster le profil sportif."""

    def __init__(
        self,
        program_repository: WorkoutProgramRepository,
        feedback_repository: WorkoutFeedbackRepository,
        profile_repository: FitnessProfileRepository,
        test_mode: bool = False,
    ) -> None:
        self._programs = program_repository
        self._feedbacks = feedback_repository
        self._profiles = profile_repository
        self._test_mode = test_mode

    async def execute(
        self,
        program_id: str,
        payload: WorkoutFeedbackRequest,
    ) -> WorkoutFeedbackResponse:
        if self._test_mode:
            profile_niveau = "debutant"
            if payload.trop_facile:
                profile_niveau = _bump_niveau(profile_niveau)
            return WorkoutFeedbackResponse(
                feedback_id="test-feedback-id",
                program_id=program_id,
                user_id=1,
                profile_niveau=profile_niveau,
                created_at=datetime.now(UTC),
            )

        if not await database.ping_mongodb():
            raise MongoUnavailableError()

        program = await self._programs.find_raw_by_id(program_id)
        if program is None:
            raise ProgramNotFoundError()

        user_id = int(program["userId"])
        feedback_doc = WorkoutFeedback(
            program_id=program_id,
            user_id=user_id,
            rating=payload.rating,
            trop_difficile=payload.trop_difficile,
            trop_facile=payload.trop_facile,
            exercices_problematiques=payload.exercices_problematiques,
        )
        feedback_id = await self._feedbacks.save(feedback_doc)

        profile = await self._profiles.find_by_user_id(user_id)
        if profile is None:
            profile = UserFitnessProfile(
                user_id=user_id,
                objectif="renforcement",
                niveau="debutant",
            )

        historique = list(profile.historique)
        historique.append(
            {
                "type": "feedback",
                "programId": program_id,
                "rating": payload.rating,
                "tropDifficile": payload.trop_difficile,
                "tropFacile": payload.trop_facile,
                "exercicesProblematiques": payload.exercices_problematiques,
                "at": datetime.now(UTC).isoformat(),
            },
        )

        limitations = _prune_expired_limitations(list(profile.limitations), historique)
        limitations, historique = _merge_temporary_limitations(
            limitations,
            payload.exercices_problematiques,
            historique,
        )

        niveau = profile.niveau
        if payload.trop_facile:
            previous_trop_facile = await self._feedbacks.count_recent_trop_facile(
                user_id,
                window_days=REPEATED_TOO_EASY_WINDOW_DAYS,
            )
            if previous_trop_facile >= 2:
                new_niveau = _bump_niveau(niveau)
                if new_niveau != niveau:
                    historique.append(
                        {
                            "type": "level_adjustment",
                            "from": niveau,
                            "to": new_niveau,
                            "reason": "trop_facile_repeated",
                            "at": datetime.now(UTC).isoformat(),
                        },
                    )
                    niveau = new_niveau

        updated_profile = profile.model_copy(
            update={
                "niveau": niveau,
                "limitations": limitations,
                "historique": historique,
            },
        )
        await self._profiles.upsert(updated_profile)

        return WorkoutFeedbackResponse(
            feedback_id=feedback_id,
            program_id=program_id,
            user_id=user_id,
            profile_niveau=niveau,
            created_at=feedback_doc.created_at,
        )
