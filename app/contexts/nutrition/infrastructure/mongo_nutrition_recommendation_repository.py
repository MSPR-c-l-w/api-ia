"""Persistance MongoDB pour les recommandations de plan repas."""

from __future__ import annotations

from datetime import UTC, datetime

from app.shared.infrastructure import collections as col
from app.shared.infrastructure import database


class MongoNutritionRecommendationRepository:
    async def save(self, user_id: int, meal_plan: dict) -> str:
        if database.get_database() is None:
            return ""
        db = database.get_database()
        doc = {
            "userId": user_id,
            "platRecommande": meal_plan.get("days", [{}])[0] if meal_plan.get("days") else {},
            "mealPlan": meal_plan.get("days", []),
            "userGoal": meal_plan.get("userGoal", ""),
            "modelStatus": meal_plan.get("modelStatus", ""),
            "createdAt": datetime.now(UTC),
        }
        result = await db[col.NUTRITION_RECOMMENDATIONS].insert_one(doc)
        return str(result.inserted_id)
