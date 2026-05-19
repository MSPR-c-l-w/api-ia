"""Planification hebdomadaire adaptative — EPIC #79 #96."""

from app.contexts.workout.domain.entities.workout_program import PlannedExercise, ProgramDay
from app.contexts.workout.domain.services.recommendation_engine import _level_index, score_exercise
from app.contexts.workout.domain.value_objects.exercise_definition import ExerciseDefinition
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring
from app.contexts.workout.domain.data.exercises_catalog import EXERCISE_CATALOG

WEEK_DAYS = [
    "lundi",
    "mardi",
    "mercredi",
    "jeudi",
    "vendredi",
    "samedi",
    "dimanche",
]

ROTATION_PENALTY = 0.3
MAX_GROUP_FREQUENCY_PER_WEEK = 2
MAX_EXERCISES_PER_SESSION = 3


def _training_days_count(level: str) -> int:
    idx = _level_index(level)
    if idx == 0:
        return 3
    if idx == 1:
        return 4
    if idx == 2:
        return 5
    return 6


def _session_duration_bounds(level: str) -> tuple[int, int]:
    idx = _level_index(level)
    if idx == 0:
        return (30, 45)
    if idx == 1:
        return (45, 60)
    if idx == 2:
        return (60, 75)
    return (60, 90)


def _exercises_per_session(training_day_count: int) -> int:
    """Adapte le volume par séance pour couvrir toute la semaine avec le catalogue."""
    if training_day_count <= 0:
        return MAX_EXERCISES_PER_SESSION
    per_day = len(EXERCISE_CATALOG) // training_day_count
    return max(1, min(MAX_EXERCISES_PER_SESSION, per_day))


def _spread_training_day_indices(count: int) -> list[int]:
    if count <= 0:
        return []
    if count >= 7:
        return list(range(7))
    if count == 1:
        return [0]
    return [int(round(i * 6 / (count - 1))) for i in range(count)]


def _score_with_rotation(
    exercise: ExerciseDefinition,
    profile: UserProfileForScoring,
    recent_exercise_ids: set[str],
    *,
    exclude_recent: bool = False,
) -> float:
    base = score_exercise(exercise, profile)
    if base <= 0:
        return 0.0
    if exercise.id in recent_exercise_ids:
        if exclude_recent:
            return 0.0
        return round(base * ROTATION_PENALTY, 4)
    return base


def _ranked_exercises(
    profile: UserProfileForScoring,
    recent_exercise_ids: set[str],
) -> list[tuple[ExerciseDefinition, float]]:
    scored = [
        (
            exercise,
            _score_with_rotation(
                exercise,
                profile,
                recent_exercise_ids,
                exclude_recent=True,
            ),
        )
        for exercise in EXERCISE_CATALOG
    ]
    return sorted(
        [(ex, sc) for ex, sc in scored if sc > 0],
        key=lambda item: item[1],
        reverse=True,
    )


def _assign_groups_to_training_days(
    groups: list[str],
    training_day_count: int,
) -> list[list[str]]:
    """Répartit les groupes musculaires (≤ 2 apparitions / semaine)."""
    if training_day_count == 0:
        return []

    day_groups: list[list[str]] = [[] for _ in range(training_day_count)]
    group_counts: dict[str, int] = dict.fromkeys(groups, 0)
    day_ptr = 0
    safety = 0

    while safety < 50 and any(
        group_counts[g] < MAX_GROUP_FREQUENCY_PER_WEEK for g in groups
    ):
        for group in groups:
            if group_counts[group] >= MAX_GROUP_FREQUENCY_PER_WEEK:
                continue
            day = day_ptr % training_day_count
            if group not in day_groups[day] and len(day_groups[day]) < 2:
                day_groups[day].append(group)
                group_counts[group] += 1
            day_ptr += 1
        safety += 1

    return day_groups


def _to_planned_exercise(
    exercise: ExerciseDefinition,
    duration_minutes: int,
) -> PlannedExercise:
    if exercise.muscle_group == "cardio":
        return PlannedExercise(id=exercise.id, duree=max(5, duration_minutes))
    return PlannedExercise(
        id=exercise.id,
        sets=3,
        reps=10 if exercise.level in {"debutant", "intermediaire"} else 12,
    )


def generate_weekly_program(
    profile: UserProfileForScoring,
    recent_exercise_ids: list[str] | None = None,
) -> list[ProgramDay]:
    """
    Génère un programme sur 7 jours avec repos, récupération musculaire et rotation.
    """
    recent = set(recent_exercise_ids or [])
    ranked = _ranked_exercises(profile, recent)
    by_group: dict[str, list[tuple[ExerciseDefinition, float]]] = {}
    for exercise, score in ranked:
        by_group.setdefault(exercise.muscle_group, []).append((exercise, score))

    training_count = _training_days_count(profile.niveau)
    training_indices = _spread_training_day_indices(training_count)
    exercises_per_session = _exercises_per_session(training_count)
    min_dur, max_dur = _session_duration_bounds(profile.niveau)
    session_duration = (min_dur + max_dur) // 2
    per_exercise_duration = max(5, session_duration // exercises_per_session)

    group_assignments = _assign_groups_to_training_days(
        sorted(by_group.keys()),
        len(training_indices),
    )

    used_exercise_ids: set[str] = set()
    programme: list[ProgramDay] = []
    training_slot = 0

    for day_index, day_name in enumerate(WEEK_DAYS):
        if day_index not in training_indices:
            programme.append(ProgramDay(jour=day_name, exercices=[]))
            continue

        groups_today = (
            group_assignments[training_slot]
            if training_slot < len(group_assignments)
            else []
        )
        training_slot += 1
        session_exercises: list[PlannedExercise] = []

        for group in groups_today:
            candidates = by_group.get(group, [])
            for exercise, _score in candidates:
                if exercise.id in used_exercise_ids:
                    continue
                session_exercises.append(
                    _to_planned_exercise(exercise, per_exercise_duration),
                )
                used_exercise_ids.add(exercise.id)
                if len(session_exercises) >= exercises_per_session:
                    break
            if len(session_exercises) >= exercises_per_session:
                break

        if len(session_exercises) < exercises_per_session:
            for exercise, _score in ranked:
                if exercise.id in used_exercise_ids:
                    continue
                session_exercises.append(
                    _to_planned_exercise(exercise, per_exercise_duration),
                )
                used_exercise_ids.add(exercise.id)
                if len(session_exercises) >= exercises_per_session:
                    break

        programme.append(ProgramDay(jour=day_name, exercices=session_exercises))

    return programme


def count_muscle_group_frequency(programme: list[ProgramDay]) -> dict[str, int]:
    """Compte les séances par groupe musculaire sur la semaine (helper tests)."""
    exercise_by_id = {ex.id: ex for ex in EXERCISE_CATALOG}
    counts: dict[str, int] = {}

    for day in programme:
        if not day.exercices:
            continue
        groups_today = {
            exercise_by_id[planned.id].muscle_group
            for planned in day.exercices
            if planned.id in exercise_by_id
        }
        for group in groups_today:
            counts[group] = counts.get(group, 0) + 1

    return counts
