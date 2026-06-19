"""Tests end-to-end : tranche verticale complète contre une vraie stack.

Marqués ``e2e`` et ignorés automatiquement si MongoDB est indisponible.

Le container est reconstruit en mode non-test (``test_mode=False``), connecté à
un vrai MongoDB, et les use cases sont exécutés bout-en-bout (use case → domaine
→ persistance → relecture) dans une seule boucle d'évènements.

Note : on ne passe pas par le client HTTP Flask car ses vues asynchrones
s'exécutent dans une boucle d'évènements distincte par requête, incompatible
avec le client Motor (cf. ``_LifespanAsgiApp`` dans ``app/main.py`` qui lie
Motor à la boucle de Hypercorn en production). On teste donc la stack applicative
complète en amont de la couche WSGI, déjà couverte par les tests de routes.

    pytest -m e2e
"""

import pytest

from app.composition.container import Container
from app.config import settings
from app.contexts.nutrition.presentation.schemas import (
    MealPlanRequest,
    NutritionAnalysisRequest,
)
from app.contexts.workout.presentation.schemas import (
    WorkoutFeedbackRequest,
    WorkoutProgramRequest,
)
from app.shared.application.exceptions import ProgramNotFoundError
from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database

pytestmark = pytest.mark.e2e

_TEST_URI = "mongodb://localhost:27017/healthai_coach_e2e?serverSelectionTimeoutMS=1500"
_COLLECTIONS = (col.WORKOUT_PROGRAMS, col.USER_FITNESS_PROFILES, col.WORKOUT_FEEDBACKS)


@pytest.fixture
async def container(monkeypatch):
    monkeypatch.setattr(settings, "environment", "e2e")
    monkeypatch.setattr(settings, "mongodb_uri", _TEST_URI)

    try:
        await database.connect_mongodb()
        available = await database.ping_mongodb()
    except Exception:
        available = False

    if not available:
        await database.close_mongodb()
        pytest.skip("MongoDB indisponible — test e2e ignoré")

    db = database.get_database()
    for name in _COLLECTIONS:
        await db[name].delete_many({})

    # Container neuf en mode non-test → vrais dépôts Mongo.
    yield Container()

    for name in _COLLECTIONS:
        await db[name].delete_many({})
    await database.close_mongodb()


async def test_full_workout_program_and_feedback_flow(container):
    # 1. Génère et persiste un programme.
    program = await container.create_workout_program.execute(
        WorkoutProgramRequest(
            userId=4242,
            objectif="renforcement",
            niveau="debutant",
            preferences=["faible impact"],
        )
    )
    assert program.program_id and program.program_id != "test-program-id"
    assert len(program.programme) == 7

    # 2. Soumet un feedback sur ce programme réel → ajuste le profil sportif.
    feedback = await container.submit_workout_feedback.execute(
        program.program_id,
        WorkoutFeedbackRequest(
            rating=5, tropFacile=True, exercicesProblematiques=["squat-pdc"]
        ),
    )
    assert feedback.user_id == 4242
    assert feedback.feedback_id != "test-feedback-id"
    assert feedback.program_id == program.program_id

    # 3. Le profil a bien été persisté avec la limitation temporaire.
    profile = await database.get_database()[col.USER_FITNESS_PROFILES].find_one(
        {"userId": 4242}
    )
    assert profile is not None
    assert any("squat-pdc" in lim for lim in profile["limitations"])


async def test_feedback_on_unknown_program_raises(container):
    with pytest.raises(ProgramNotFoundError):
        await container.submit_workout_feedback.execute(
            "507f1f77bcf86cd799439011",
            WorkoutFeedbackRequest(rating=3),
        )


async def test_recent_exercise_rotation_persisted(container):
    # Deux générations consécutives pour le même utilisateur : la seconde
    # relit les exercices récents depuis Mongo (rotation anti-répétition).
    first = await container.create_workout_program.execute(
        WorkoutProgramRequest(userId=99, objectif="renforcement", niveau="avance")
    )
    second = await container.create_workout_program.execute(
        WorkoutProgramRequest(userId=99, objectif="renforcement", niveau="avance")
    )

    assert first.program_id != second.program_id
    count = await database.get_database()[col.WORKOUT_PROGRAMS].count_documents(
        {"userId": 99}
    )
    assert count == 2


async def test_nutrition_analyze_flow(container):
    result = await container.analyze_meal.execute(
        NutritionAnalysisRequest(
            imageUrl="https://example.com/meal.jpg", userGoal="equilibre"
        )
    )
    assert result.detected_foods is not None
    assert len(result.feedback) > 0


async def test_nutrition_meal_plan_flow(container):
    result = await container.generate_meal_plan.execute(
        MealPlanRequest(
            userGoal="perte_de_poids",
            dietaryConstraints=["vegetarien"],
            allergies=["arachide"],
        )
    )
    assert len(result.days) == 7
