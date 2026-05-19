from app.contexts.nutrition.presentation.schemas import (
    DailyMealPlan,
    MealPlanRequest,
    MealPlanResponse,
)


class GenerateMealPlanUseCase:
    """Use case : générer un plan repas hebdomadaire (stub local)."""

    async def execute(self, payload: MealPlanRequest) -> MealPlanResponse:
        constraints = {item.lower() for item in payload.dietary_constraints}
        allergies = {item.lower() for item in payload.allergies}

        protein_main = "tofu mariné" if "vegetarien" in constraints else "poulet grillé"
        fish_main = "tempeh laqué" if "vegetarien" in constraints else "saumon"

        snack = "Amandes" if "arachide" not in allergies else "Yaourt nature"

        days = []
        for day in range(1, 8):
            calories = payload.daily_calories_target or (1900 if payload.user_goal == "perte_de_poids" else 2300)
            days.append(
                DailyMealPlan(
                    day=day,
                    breakfast="Skyr, fruits rouges et flocons d'avoine",
                    lunch=f"Bowl quinoa, legumes rôtis et {protein_main}",
                    dinner=f"{fish_main}, legumes verts et patate douce",
                    snack=snack,
                    estimatedCalories=calories,
                ),
            )

        return MealPlanResponse(
            userGoal=payload.user_goal,
            days=days,
            notes=[
                "Plan généré en mode stub local.",
                "Les préférences et contraintes déclarées sont prises en compte.",
            ],
            modelStatus="stub_ready_for_llm",
        )
