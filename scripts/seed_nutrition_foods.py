"""Seed MongoDB — collection ``nutrition_foods`` (catalogue d'aliments).

Source des données, par ordre de priorité :
  1. La table ``Nutrition`` du backend NestJS (données Kaggle validées), via
     ``GET /nutrition`` paginé (compte service JWT).
  2. À défaut (backend indisponible ou credentials absents), la table statique
     embarquée ``nutrition_lookup._TABLE``.

Les documents sont insérés en upsert sur ``name`` (clé unique). Format aligné
sur l'adaptateur ``MongoNutritionLookupService``.

Usage:
    python scripts/seed_nutrition_foods.py
"""

import asyncio
import os
import sys
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.contexts.nutrition.infrastructure.backend_auth import (
    BackendAuthService,  # noqa: E402
)
from app.contexts.nutrition.infrastructure.nutrition_lookup import _TABLE  # noqa: E402
from app.shared.infrastructure import collections as col  # noqa: E402

_PAGE_SIZE = 100


def _fetch_from_backend() -> list[dict[str, Any]]:
    """Récupère tous les aliments validés depuis le backend NestJS."""
    if not settings.backend_service_email or not settings.backend_service_password:
        print("BACKEND_SERVICE_EMAIL/PASSWORD absents — fallback table statique.")
        return []

    try:
        auth = BackendAuthService(
            backend_url=settings.backend_url,
            email=settings.backend_service_email,
            password=settings.backend_service_password,
            timeout_seconds=settings.backend_timeout_seconds,
        )
        token = auth.get_token()
    except Exception as exc:  # noqa: BLE001
        print(f"Auth backend impossible ({exc}) — fallback table statique.")
        return []

    headers = {"Authorization": f"Bearer {token}"}
    url = f"{settings.backend_url.rstrip('/')}/nutrition"
    items: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=settings.backend_timeout_seconds) as client:
            for page in range(1, 1000):
                resp = client.get(
                    url, params={"page": page, "limit": _PAGE_SIZE}, headers=headers
                )
                resp.raise_for_status()
                batch: list[dict[str, Any]] = resp.json().get("data", [])
                items.extend(batch)
                if len(batch) < _PAGE_SIZE:
                    break
    except Exception as exc:  # noqa: BLE001
        print(f"Lecture /nutrition impossible ({exc}) — fallback table statique.")
        return []

    print(f"{len(items)} aliments récupérés depuis le backend.")
    return [
        {
            "name": item.get("name"),
            "calories_kcal": item.get("calories_kcal"),
            "protein_g": item.get("protein_g"),
            "carbohydrates_g": item.get("carbohydrates_g"),
            "fat_g": item.get("fat_g"),
            "fiber_g": item.get("fiber_g"),
            "category": item.get("category"),
        }
        for item in items
        if item.get("name")
    ]


def _fetch_from_static() -> list[dict[str, Any]]:
    """Construit le catalogue depuis la table statique embarquée."""
    docs: list[dict[str, Any]] = []
    for name, (kcal, prot, carb, fat, fib) in _TABLE.items():
        docs.append(
            {
                "name": name,
                "calories_kcal": kcal,
                "protein_g": prot,
                "carbohydrates_g": carb,
                "fat_g": fat,
                "fiber_g": fib,
                "category": "static",
            }
        )
    print(f"{len(docs)} aliments construits depuis la table statique.")
    return docs


async def main() -> None:
    docs = _fetch_from_backend() or _fetch_from_static()
    if not docs:
        print("Aucun aliment à insérer — abandon.")
        return

    client = AsyncIOMotorClient(settings.mongodb_uri, serverSelectionTimeoutMS=5000)
    db = client.get_default_database()
    coll = db[col.NUTRITION_FOODS]
    await coll.create_index("name", unique=True)

    upserts = 0
    for doc in docs:
        await coll.update_one({"name": doc["name"]}, {"$set": doc}, upsert=True)
        upserts += 1

    total = await coll.count_documents({})
    print(f"{upserts} aliments upsertés. Total en base : {total}.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
