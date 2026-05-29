"""Moteur de composition de repas basé sur les 601 aliments Kaggle.

Algorithme :
1. Classifie chaque aliment par catégorie dominante (protéine, glucide, légume, etc.)
2. Pour chaque slot de repas (petit-déj / déj / dîner), cherche la combinaison
   de 2-3 aliments qui minimise l'écart aux macros cibles.
3. Scale les portions pour atteindre la cible calorique du slot (×1, ×2, ×3…)
4. Fait varier les combinaisons sur 7 jours (rotation des candidats).

Score d'un repas = 1 − mean(|deviation_i / target_i|) ∈ [0, 1]
Plus le score est proche de 1, plus les macros du repas sont proches des cibles.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from app.contexts.nutrition.domain.models import HealthProfile, Macros


class FoodCategory(str, Enum):
    PROTEIN = "protein"       # viandes, poissons, œufs, légumineuses
    CARB = "carb"             # céréales, pâtes, riz, pain
    VEGETABLE = "vegetable"   # légumes (<80 kcal/portion, fibres élevées)
    BREAKFAST = "breakfast"   # spécifiques petit-déj (avoine, yaourt, fruits…)
    MIXED = "mixed"           # autre / équilibré


@dataclass
class FoodItem:
    name: str
    macros: Macros
    category: FoodCategory


@dataclass
class ComposedMeal:
    foods: list[str]
    macros: Macros
    score: float                  # 0-1, 1 = cible parfaite
    deviation_pcts: dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Classifieur d'aliments
# ---------------------------------------------------------------------------

import re as _re

_BREAKFAST_KEYWORDS = {
    # Céréales / féculents matin
    "avoine", "porridge", "granola", "muesli", "müsli", "cereal",
    "flocon", "corn flakes", "weetabix",
    # Produits laitiers / œufs
    "yaourt", "yogurt", "skyr", "fromage blanc", "kéfir",
    "œuf", "omelette", "egg",
    # Viennoiseries / pains sucrés
    "pancake", "crêpe", "toast", "tartine", "bagel", "brioche",
    "muffin", "scone", "gaufre", "waffle",
    # Fruits (consommés le matin)
    "smoothie", "bowl", "fruit",
    "banane", "pomme", "fraise", "framboise", "myrtille", "mangue",
    "orange", "pamplemousse", "melon", "pastèque", "kiwi",
    "ananas", "poire", "pêche", "nectarine", "abricot",
    # Autres typiques matin
    "confiture", "miel", "beurre de cacahuète", "beurre d'arachide",
    "jus d'orange", "jus de fruit",
}

_VEGETABLE_KEYWORDS = {
    "artichaut", "asperge", "aubergine", "brocoli", "carotte",
    "champignon", "chou", "courgette", "épinard", "haricot vert",
    "laitue", "poivron", "radis", "salade", "tomate", "concombre",
    "ail", "oignon", "céleri", "fenouil", "petits pois",
}

# Mots qui indiquent clairement un plat de déjeuner/dîner (pas petit-déj)
_LUNCH_DINNER_KEYWORDS = {
    "burger", "pizza", "pâte", "riz", "pasta", "sandwich",
    "soupe", "ragoût", "curry", "sauté", "rôti", "grillé",
    "fajita", "tacos", "burrito", "sushi", "ramen", "pho",
}


def _is_breakfast(name_l: str) -> bool:
    """Retourne True si le nom contient un mot-clé petit-déj (correspondance mot entier)."""
    for kw in _BREAKFAST_KEYWORDS:
        # Correspondance mot entier pour éviter les faux positifs (ex: bœuf ≠ œuf)
        pattern = r"(?<![a-zA-ZÀ-ÿœæ])" + _re.escape(kw) + r"(?![a-zA-ZÀ-ÿœæ])"
        if _re.search(pattern, name_l):
            return True
    return False


def _classify(name: str, macros: Macros) -> FoodCategory:
    name_l = name.lower()

    # Exclure explicitement les plats de déjeuner/dîner avant la détection breakfast
    if any(kw in name_l for kw in _LUNCH_DINNER_KEYWORDS):
        # Laisse passer aux règles suivantes
        pass
    elif _is_breakfast(name_l):
        return FoodCategory.BREAKFAST

    # Légume : peu calorique + fibres ou mot-clé
    if macros.calories < 80 and (macros.fibers_g > 1.5 or any(kw in name_l for kw in _VEGETABLE_KEYWORDS)):
        return FoodCategory.VEGETABLE

    # Protéine dominante : ratio prot/cal > 0.12 et quantité absolue > 8g
    if macros.calories > 0:
        if macros.proteins_g / macros.calories > 0.12 and macros.proteins_g > 8:
            return FoodCategory.PROTEIN

    # Glucide dominant : carbs > 20g et ratio carb/cal > 0.5
    if macros.calories > 0:
        if macros.carbs_g > 20 and macros.carbs_g * 4 / macros.calories > 0.5:
            return FoodCategory.CARB

    return FoodCategory.MIXED


# ---------------------------------------------------------------------------
# Scoring d'un repas assemblé
# ---------------------------------------------------------------------------

_NUTRIENT_WEIGHTS = {
    "calories": 1.5,
    "proteins_g": 1.2,
    "carbs_g": 1.0,
    "fats_g": 1.0,
    "fibers_g": 0.8,
}

# Portion scaling : limites pour éviter les aberrations (0.5x à 4x la portion)
_MIN_SCALE = 0.5
_MAX_SCALE = 4.0


def _score_meal(combined: Macros, target: Macros) -> tuple[float, dict[str, float]]:
    """Calcule le score (0-1) et les déviations d'un repas vs sa cible."""
    deviations: dict[str, float] = {}
    total_w = sum(_NUTRIENT_WEIGHTS.values())
    weighted_dev = 0.0

    for nutrient, weight in _NUTRIENT_WEIGHTS.items():
        actual = getattr(combined, nutrient)
        t = getattr(target, nutrient)
        dev = abs(actual - t) / t if t > 0 else 0.0
        deviations[nutrient] = round((actual - t) / t * 100 if t > 0 else 0.0, 1)
        weighted_dev += weight * min(dev, 1.0)  # cap à 100% d'écart

    score = max(0.0, 1.0 - weighted_dev / total_w)
    return round(score, 4), deviations


def _combine_macros(foods: list[FoodItem]) -> Macros:
    return Macros(
        calories=sum(f.macros.calories for f in foods),
        proteins_g=sum(f.macros.proteins_g for f in foods),
        carbs_g=sum(f.macros.carbs_g for f in foods),
        fats_g=sum(f.macros.fats_g for f in foods),
        fibers_g=sum(f.macros.fibers_g for f in foods),
    )


def _scale_to_target(
    selected: list[FoodItem],
    target_cal: float,
) -> tuple[list[str], Macros]:
    """Scale les portions pour atteindre la cible calorique.

    Chaque aliment reçoit le même facteur de scaling, arrondi à l'entier le plus
    proche (minimum ×½). Les portions sont toujours des entiers : ×1, ×2, ×3…

    Exemples de noms :
    - scale=1  → "poulet grillé"         (inchangé, portion standard)
    - scale=2  → "poulet grillé ×2"      (double portion)
    - scale=0.5 → "poulet grillé ×½"    (demi-portion)
    """
    total_cal = sum(f.macros.calories for f in selected)
    if total_cal <= 0 or target_cal <= 0:
        return [f.name for f in selected], _combine_macros(selected)

    raw_scale = target_cal / total_cal
    # Arrondi à l'entier le plus proche, borné entre 0.5 et _MAX_SCALE
    clamped = max(_MIN_SCALE, min(_MAX_SCALE, raw_scale))
    scale = 0.5 if clamped <= 0.75 else max(1, round(clamped))

    scaled_names = []
    for f in selected:
        if scale == 1:
            scaled_names.append(f.name)
        elif scale == 0.5:
            scaled_names.append(f"{f.name} ×½")
        else:
            scaled_names.append(f"{f.name} ×{int(scale)}")

    scaled_macros = Macros(
        calories=round(total_cal * scale),
        proteins_g=round(sum(f.macros.proteins_g for f in selected) * scale, 1),
        carbs_g=round(sum(f.macros.carbs_g for f in selected) * scale, 1),
        fats_g=round(sum(f.macros.fats_g for f in selected) * scale, 1),
        fibers_g=round(sum(f.macros.fibers_g for f in selected) * scale, 1),
    )
    return scaled_names, scaled_macros


# ---------------------------------------------------------------------------
# Moteur de composition
# ---------------------------------------------------------------------------

_MEAL_FRACTION = {
    "breakfast": 0.25,
    "lunch": 0.35,
    "dinner": 0.30,
    "snack": 0.10,
}


class MealComposerService:
    """Compose des repas équilibrés à partir du catalogue d'aliments.

    Usage ::

        from app.contexts.nutrition.infrastructure.backend_nutrition_lookup import BackendNutritionLookupService
        catalog = svc._table   # {name: (cal, prot, carb, fat, fiber)}
        composer = MealComposerService(catalog)
        plan = composer.compose_week(health_profile, constraints={"vegetarien"})
    """

    def __init__(
        self,
        catalog: dict[str, tuple[float, float, float, float, float]],
        rng_seed: int | None = None,
    ) -> None:
        self._rng = random.Random(rng_seed)
        self._items: list[FoodItem] = self._build_items(catalog)
        self._by_category: dict[FoodCategory, list[FoodItem]] = {
            cat: [] for cat in FoodCategory
        }
        for item in self._items:
            self._by_category[item.category].append(item)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compose_week(
        self,
        profile: HealthProfile,
        constraints: set[str] | None = None,
        allergies: set[str] | None = None,
    ) -> list[dict[str, str | int | float]]:
        """Retourne 7 jours de repas sous forme de dicts.

        Chaque jour : {"breakfast", "lunch", "dinner", "snack", "score",
                       "estimatedCalories"}
        """
        constraints = {c.lower() for c in (constraints or [])}
        allergies = {a.lower() for a in (allergies or [])}

        # Filtre le catalogue selon les contraintes
        allowed = self._filter_catalog(constraints, allergies)

        days = []
        # Exclure tous les aliments récemment utilisés (fenêtre glissante sur 2 jours)
        # pour garantir de la variété inter-journalière sur tous les slots.
        used_recent: list[str] = []

        for day in range(1, 8):
            # Réinitialise l'exclusion tous les 3 jours pour permettre les cycles
            if day % 3 == 1:
                used_recent = []

            breakfast_target = self._meal_target(profile, "breakfast")
            lunch_target = self._meal_target(profile, "lunch")
            dinner_target = self._meal_target(profile, "dinner")
            snack_target = self._meal_target(profile, "snack")

            day_used: list[str] = []  # aliments utilisés aujourd'hui

            breakfast = self._compose_slot(
                allowed, ["breakfast", "carb"], breakfast_target,
                n_foods=2, exclude=used_recent, day_offset=day,
            )
            day_used += [f.split(" ×")[0] for f in breakfast.foods]

            lunch = self._compose_slot(
                allowed, ["protein", "carb", "vegetable", "mixed"], lunch_target,
                n_foods=3, exclude=used_recent + day_used, day_offset=day,
            )
            day_used += [f.split(" ×")[0] for f in lunch.foods]

            dinner = self._compose_slot(
                allowed, ["protein", "vegetable", "mixed", "carb"], dinner_target,
                n_foods=3, exclude=used_recent + day_used, day_offset=day + 7,
            )
            day_used += [f.split(" ×")[0] for f in dinner.foods]

            snack = self._compose_slot(
                allowed, ["mixed", "vegetable", "breakfast"], snack_target,
                n_foods=1, exclude=used_recent + day_used, day_offset=day + 14,
            )
            day_used += [f.split(" ×")[0] for f in snack.foods]

            # Cumule les aliments du jour dans la fenêtre d'exclusion
            for name in day_used:
                if name not in used_recent:
                    used_recent.append(name)

            total_cal = int(
                breakfast.macros.calories
                + lunch.macros.calories
                + dinner.macros.calories
                + snack.macros.calories
            )
            avg_score = round(
                (breakfast.score + lunch.score + dinner.score) / 3, 3
            )

            days.append({
                "day": day,
                "breakfast": ", ".join(breakfast.foods),
                "lunch": ", ".join(lunch.foods),
                "dinner": ", ".join(dinner.foods),
                "snack": snack.foods[0] if snack.foods else None,
                "estimatedCalories": total_cal,
                "score": avg_score,
            })

        return days

    def score_meal(
        self,
        food_names: list[str],
        profile: HealthProfile,
        slot: str = "lunch",
    ) -> ComposedMeal:
        """Score un repas existant vs les cibles du profil."""
        items = [i for i in self._items if i.name in food_names]
        if not items:
            macros = Macros(0, 0, 0, 0, 0)
            return ComposedMeal(foods=food_names, macros=macros, score=0.0)
        combined = _combine_macros(items)
        target = self._meal_target(profile, slot)
        score, devs = _score_meal(combined, target)
        return ComposedMeal(foods=food_names, macros=combined, score=score, deviation_pcts=devs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_items(
        catalog: dict[str, tuple[float, float, float, float, float]],
    ) -> list[FoodItem]:
        items = []
        for name, (cal, prot, carbs, fat, fiber) in catalog.items():
            # Ignore aliments quasi sans valeur nutritive (ex: angostura bitters)
            if cal < 2 and prot < 0.5 and carbs < 0.5:
                continue
            macros = Macros(
                calories=cal,
                proteins_g=prot,
                carbs_g=carbs,
                fats_g=fat,
                fibers_g=fiber,
            )
            items.append(FoodItem(name=name, macros=macros, category=_classify(name, macros)))
        return items

    @staticmethod
    def _meal_target(profile: HealthProfile, slot: str) -> Macros:
        frac = _MEAL_FRACTION.get(slot, 1 / 3)
        return Macros(
            calories=profile.daily_calories_target * frac,
            proteins_g=profile.proteins_target_g * frac,
            carbs_g=profile.carbs_target_g * frac,
            fats_g=profile.fats_target_g * frac,
            fibers_g=profile.fibers_target_g * frac,
        )

    def _filter_catalog(
        self,
        constraints: set[str],
        allergies: set[str],
    ) -> list[FoodItem]:
        """Retire les aliments incompatibles avec les contraintes."""
        _MEAT_KEYWORDS = {"poulet", "bœuf", "porc", "agneau", "veau", "canard",
                          "dinde", "jambon", "saucisse", "bacon", "steak", "bifteck",
                          "côtelette", "filet", "rôti", "viande"}
        _FISH_KEYWORDS = {"saumon", "thon", "cabillaud", "dorade", "crevette",
                          "homard", "moule", "huître", "maquereau", "sardine",
                          "anchois", "fruits de mer", "poisson"}

        is_vegetarian = "vegetarien" in constraints or "végétarien" in constraints
        is_vegan = "vegan" in constraints or "végétalien" in constraints

        result = []
        for item in self._items:
            name_l = item.name.lower()

            if is_vegetarian or is_vegan:
                if any(kw in name_l for kw in _MEAT_KEYWORDS | _FISH_KEYWORDS):
                    continue

            if is_vegan:
                _ANIMAL_KEYWORDS = {"fromage", "lait", "crème", "beurre", "yaourt",
                                    "yogurt", "œuf", "egg", "miel", "honey"}
                if any(kw in name_l for kw in _ANIMAL_KEYWORDS):
                    continue

            if any(allergy in name_l for allergy in allergies):
                continue

            result.append(item)

        return result

    def _compose_slot(
        self,
        allowed: list[FoodItem],
        category_priority: list[str],
        target: Macros,
        n_foods: int,
        exclude: list[str],
        day_offset: int = 0,
    ) -> ComposedMeal:
        """Sélectionne la meilleure combinaison de n_foods aliments pour ce slot,
        puis scale les portions pour atteindre la cible calorique."""
        # Construit un pool de candidats en respectant la priorité de catégories
        pool: list[FoodItem] = []
        used_names = set(exclude)

        for cat_name in category_priority:
            try:
                cat = FoodCategory(cat_name)
            except ValueError:
                continue
            candidates = [
                i for i in allowed
                if i.category == cat and i.name not in used_names
            ]
            if candidates:
                # Rotation déterministe par day_offset
                start = day_offset % len(candidates)
                rotated = candidates[start:] + candidates[:start]
                pool.extend(rotated[:min(8, len(rotated))])
            if len(pool) >= n_foods * 4:
                break

        # Fallback niveau 1 : tous les aliments permis (hors exclusions)
        if len(pool) < n_foods:
            pool = [i for i in allowed if i.name not in used_names]

        # Fallback niveau 2 : catalogue complet si les exclusions ont tout éliminé
        if len(pool) < n_foods:
            pool = list(allowed)

        if not pool:
            return ComposedMeal(foods=[], macros=Macros(0, 0, 0, 0, 0), score=0.0)

        # Essai greedy : choisit le 1er aliment, puis complémente
        best: ComposedMeal | None = None

        # Nombre de candidats de départ à tester (limité pour la perf)
        starters = pool[:min(n_foods * 3, len(pool))]

        for starter in starters:
            selected = [starter]
            remaining_target = Macros(
                calories=max(0, target.calories - starter.macros.calories),
                proteins_g=max(0, target.proteins_g - starter.macros.proteins_g),
                carbs_g=max(0, target.carbs_g - starter.macros.carbs_g),
                fats_g=max(0, target.fats_g - starter.macros.fats_g),
                fibers_g=max(0, target.fibers_g - starter.macros.fibers_g),
            )

            for _ in range(n_foods - 1):
                complement_pool = [
                    i for i in pool
                    if i.name not in {s.name for s in selected}
                ]
                if not complement_pool:
                    break
                # Choisit le complément qui minimise l'écart restant sur les calories
                best_complement = min(
                    complement_pool,
                    key=lambda i: abs(i.macros.calories - remaining_target.calories),
                )
                selected.append(best_complement)
                remaining_target = Macros(
                    calories=max(0, remaining_target.calories - best_complement.macros.calories),
                    proteins_g=max(0, remaining_target.proteins_g - best_complement.macros.proteins_g),
                    carbs_g=max(0, remaining_target.carbs_g - best_complement.macros.carbs_g),
                    fats_g=max(0, remaining_target.fats_g - best_complement.macros.fats_g),
                    fibers_g=max(0, remaining_target.fibers_g - best_complement.macros.fibers_g),
                )

            # Scale les portions pour atteindre la cible calorique
            scaled_names, scaled_macros = _scale_to_target(selected, target.calories)
            score, devs = _score_meal(scaled_macros, target)
            candidate = ComposedMeal(
                foods=scaled_names,
                macros=scaled_macros,
                score=score,
                deviation_pcts=devs,
            )

            if best is None or candidate.score > best.score:
                best = candidate

        return best or ComposedMeal(foods=[], macros=Macros(0, 0, 0, 0, 0), score=0.0)
