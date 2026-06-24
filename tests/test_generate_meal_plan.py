"""Tests unitaires du use case GenerateMealPlan (LLM > composer > stub)."""

import json

from app.contexts.nutrition.application.use_cases.generate_meal_plan import (
    GenerateMealPlanUseCase,
)
from app.contexts.nutrition.presentation.schemas import MealPlanRequest


class FakeLlm:
    def __init__(self, plan_text=None):
        self._plan_text = plan_text

    async def generate_meal_plan_text(self, **kwargs):
        return self._plan_text


class FakeLookup:
    def __init__(self, catalog=None, raise_attr=False):
        self._catalog = catalog or {}
        self._raise_attr = raise_attr

    async def get_catalog(self):
        if self._raise_attr:
            raise AttributeError("no catalog")
        return self._catalog


def _payload(goal="equilibre", constraints=None, allergies=None, budget=None):
    return MealPlanRequest(
        userGoal=goal,
        dietaryConstraints=constraints or [],
        allergies=allergies or [],
        budget=budget,
    )


def _seven_days_json():
    days = [
        {
            "day": i,
            "breakfast": "avoine",
            "lunch": "poulet riz",
            "dinner": "saumon légumes",
            "snack": "amandes",
            "estimatedCalories": 2000,
        }
        for i in range(1, 8)
    ]
    return json.dumps({"days": days})


def _rich_catalog():
    return {
        "poulet grillé": (165, 31, 0, 4, 0, 0, 0, 0),
        "riz complet": (130, 3, 28, 1, 2, 0, 0, 0),
        "saumon": (208, 20, 0, 13, 0, 0, 0, 0),
        "brocoli": (34, 3, 7, 0, 3, 0, 0, 0),
        "flocons d'avoine": (380, 13, 67, 7, 10, 0, 0, 0),
        "yaourt grec": (59, 10, 4, 0, 0, 0, 0, 0),
        "amandes": (579, 21, 22, 50, 12, 0, 0, 0),
        "lentilles": (116, 9, 20, 0, 8, 0, 0, 0),
    }


# ---------------------------------------------------------------------------
# Chemin LLM
# ---------------------------------------------------------------------------


async def test_llm_plan_active():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=_seven_days_json())
    )

    result = await use_case.execute(_payload())

    assert result.model_status == "llm_active"
    assert len(result.days) == 7


async def test_llm_plan_notes_mention_budget_when_provided():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=_seven_days_json())
    )

    result = await use_case.execute(_payload(budget=150.0))

    assert any("150" in note for note in result.notes)


async def test_llm_plan_notes_omit_budget_when_absent():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=_seven_days_json())
    )

    result = await use_case.execute(_payload())

    assert not any("udget" in note for note in result.notes)


async def test_budget_forwarded_to_llm_provider():
    received_kwargs = {}

    class RecordingLlm(FakeLlm):
        async def generate_meal_plan_text(self, **kwargs):
            received_kwargs.update(kwargs)
            return self._plan_text

    use_case = GenerateMealPlanUseCase(
        llm_provider=RecordingLlm(plan_text=_seven_days_json())
    )

    await use_case.execute(_payload(budget=200.0))

    assert received_kwargs["budget"] == 200.0


async def test_llm_plan_wrapped_in_response_field():
    body = json.dumps({"response": f"Voici le plan : {_seven_days_json()}"})
    use_case = GenerateMealPlanUseCase(llm_provider=FakeLlm(plan_text=body))

    result = await use_case.execute(_payload())

    assert result.model_status == "llm_active"


async def test_llm_plan_rejected_when_not_seven_days():
    bad = json.dumps({"days": [{"day": 1, "breakfast": "x"}]})
    use_case = GenerateMealPlanUseCase(llm_provider=FakeLlm(plan_text=bad))

    result = await use_case.execute(_payload())

    # Plan LLM invalide → bascule sur le stub statique (pas de lookup fourni).
    assert result.model_status == "stub_ready_for_llm"


async def test_llm_plan_rejected_when_invalid_json():
    use_case = GenerateMealPlanUseCase(llm_provider=FakeLlm(plan_text="pas du json"))

    result = await use_case.execute(_payload())

    assert result.model_status == "stub_ready_for_llm"


# ---------------------------------------------------------------------------
# Chemin composer (catalogue réel)
# ---------------------------------------------------------------------------


async def test_composer_plan_when_catalog_available():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=None),
        nutrition_lookup=FakeLookup(catalog=_rich_catalog()),
    )

    result = await use_case.execute(_payload(constraints=["vegetarien"]))

    assert result.model_status == "composer_active"
    assert len(result.days) == 7


async def test_composer_skipped_when_catalog_empty():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=None),
        nutrition_lookup=FakeLookup(catalog={}),
    )

    result = await use_case.execute(_payload())

    assert result.model_status == "stub_ready_for_llm"


async def test_composer_skipped_on_attribute_error():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=None),
        nutrition_lookup=FakeLookup(raise_attr=True),
    )

    result = await use_case.execute(_payload())

    assert result.model_status == "stub_ready_for_llm"


# ---------------------------------------------------------------------------
# Chemin stub (dernier recours)
# ---------------------------------------------------------------------------


async def test_composer_failure_falls_back_to_stub(monkeypatch):
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(plan_text=None),
        nutrition_lookup=FakeLookup(catalog=_rich_catalog()),
    )

    # MealComposerService.compose_week lève → fallback stub.
    import app.contexts.nutrition.domain.meal_composer as mc

    class _Boom:
        def __init__(self, *a, **k):
            pass

        def compose_week(self, *a, **k):
            raise RuntimeError("composer boom")

    monkeypatch.setattr(mc, "MealComposerService", _Boom)

    result = await use_case.execute(_payload())

    assert result.model_status == "stub_ready_for_llm"


async def test_catalog_size_none_lookup():
    use_case = GenerateMealPlanUseCase(llm_provider=FakeLlm(), nutrition_lookup=None)

    assert await use_case._catalog_size() == 0


async def test_catalog_size_attribute_error():
    use_case = GenerateMealPlanUseCase(
        llm_provider=FakeLlm(), nutrition_lookup=FakeLookup(raise_attr=True)
    )

    assert await use_case._catalog_size() == 0


async def test_stub_plan_without_llm_or_lookup():
    use_case = GenerateMealPlanUseCase(llm_provider=FakeLlm(plan_text=None))

    result = await use_case.execute(
        _payload(constraints=["vegetarien"], allergies=["arachide"])
    )

    assert result.model_status == "stub_ready_for_llm"
    assert len(result.days) == 7
    # Les contraintes végé/allergies modifient le contenu du plan statique.
    assert "tofu" in result.days[0].lunch.lower()
    assert result.days[0].snack != "Amandes"
