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
import re
import sys
import unicodedata
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

# ---------------------------------------------------------------------------
# Génération d'alias : faire correspondre les noms verbeux des tables backend
# (« Brocolis vapeur 100g ») aux labels simples des modèles de vision
# (« broccoli »). Le lookup MongoDB résout ensuite via le champ ``aliases``.
# ---------------------------------------------------------------------------

# Tokens de quantité / préparation à retirer pour isoler le mot-aliment.
_NOISE = re.compile(r"\b\d+\s*(?:g|kg|ml|cl|l|kcal|%)\b|\bx\s*\d+\b|\b\d+\b|%")
_PREP_WORDS = {
    "vapeur",
    "grille",
    "grillee",
    "grilles",
    "grillees",
    "cuit",
    "cuite",
    "cuits",
    "cru",
    "crue",
    "crus",
    "brouille",
    "brouilles",
    "nature",
    "frais",
    "fraiche",
    "bio",
    "basmati",
    "verte",
    "vert",
    "blanc",
    "blanche",
    "poele",
    "poelee",
    "roti",
    "rotie",
    "mixte",
    "entier",
    "entiere",
    "demi",
    "ecreme",
    "ecremee",
    "de",
    "d",
    "l",
    "a",
    "au",
    "aux",
    "en",
}
# Mot-aliment (normalisé, singulier) -> variantes (FR + EN courants en vision).
_LEXICON = {
    "banane": ["banana"],
    "brocoli": ["broccoli", "brocolis"],
    "avoine": ["oats", "oatmeal", "porridge", "flocons"],
    "fromage": ["cheese", "cottage cheese"],
    "oeuf": ["egg", "eggs", "scrambled eggs"],
    "pomme": ["apple"],
    "poulet": ["chicken"],
    "riz": ["rice"],
    "salade": ["salad", "lettuce", "greens"],
    "saumon": ["salmon", "fish"],
    # Extensions courantes pour de futurs imports ETL.
    "boeuf": ["beef"],
    "porc": ["pork"],
    "pain": ["bread"],
    "pates": ["pasta"],
    "tomate": ["tomato"],
    "carotte": ["carrot"],
    "yaourt": ["yogurt"],
    "lait": ["milk"],
    "thon": ["tuna"],
    "dinde": ["turkey"],
    "jambon": ["ham"],
}


def _normalise(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower()).replace("'", " ")
    no_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", no_accents).strip()


def _singular(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") else word


def build_aliases(name: str) -> list[str]:
    """Dérive des alias (FR simplifié + EN) depuis un nom de table verbeux."""
    core = _NOISE.sub(" ", _normalise(name))
    words = [w for w in core.split() if w and w not in _PREP_WORDS]
    aliases: set[str] = set()
    if words:
        aliases.add(" ".join(words))  # noyau complet sans quantité/préparation
    for word in words:
        singular = _singular(word)
        aliases.update({word, singular})
        aliases.update(_LEXICON.get(singular, []))
        aliases.update(_LEXICON.get(word, []))
    aliases.discard("")
    return sorted(aliases)


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
            "aliases": build_aliases(item.get("name") or ""),
            "calories_kcal": item.get("calories_kcal"),
            "protein_g": item.get("protein_g"),
            "carbohydrates_g": item.get("carbohydrates_g"),
            "fat_g": item.get("fat_g"),
            "fiber_g": item.get("fiber_g"),
            "sugar_g": item.get("sugar_g"),
            "sodium_mg": item.get("sodium_mg"),
            "cholesterol_mg": item.get("cholesterol_mg"),
            "meal_type_name": item.get("meal_type_name"),
            "category": item.get("category"),
        }
        for item in items
        if item.get("name")
    ]


def _fetch_from_static() -> list[dict[str, Any]]:
    """Construit le catalogue depuis la table statique embarquée."""
    docs: list[dict[str, Any]] = []
    for name, (
        kcal,
        prot,
        carb,
        fat,
        fib,
        sugar,
        sodium,
        cholesterol,
    ) in _TABLE.items():
        docs.append(
            {
                "name": name,
                "aliases": build_aliases(name),
                "calories_kcal": kcal,
                "protein_g": prot,
                "carbohydrates_g": carb,
                "fat_g": fat,
                "fiber_g": fib,
                "sugar_g": sugar,
                "sodium_mg": sodium,
                "cholesterol_mg": cholesterol,
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
