"""Embedded nutrition reference table for offline macro estimation (#86).

Values are given per 100 g of the food.
For foods absent from the table, default estimates are used and the result is
flagged with ``estimated=True``.
"""

from __future__ import annotations

import logging

from app.contexts.nutrition.domain.models import Macros

logger = logging.getLogger(__name__)

# fmt: off
# key: lowercase token(s) that may appear in a detected food label
# values: calories (kcal), proteins_g, carbs_g, fats_g, fibers_g  – all per 100 g
_TABLE: dict[str, tuple[float, float, float, float, float]] = {
    "poulet":          (165, 31.0,  0.0,  3.6, 0.0),
    "chicken":         (165, 31.0,  0.0,  3.6, 0.0),
    "riz":             (130,  2.7, 28.0,  0.3, 0.4),
    "rice":            (130,  2.7, 28.0,  0.3, 0.4),
    "saumon":          (208, 20.0,  0.0, 13.0, 0.0),
    "salmon":          (208, 20.0,  0.0, 13.0, 0.0),
    "boeuf":           (250, 26.0,  0.0, 16.0, 0.0),
    "beef":            (250, 26.0,  0.0, 16.0, 0.0),
    "porc":            (242, 27.0,  0.0, 14.0, 0.0),
    "pork":            (242, 27.0,  0.0, 14.0, 0.0),
    "tofu":            ( 76,  8.0,  1.9,  4.8, 0.3),
    "oeuf":            (155, 13.0,  1.1, 11.0, 0.0),
    "egg":             (155, 13.0,  1.1, 11.0, 0.0),
    "lentille":        (116,  9.0, 20.0,  0.4, 8.0),
    "lentil":          (116,  9.0, 20.0,  0.4, 8.0),
    "pois":            ( 81,  5.4, 14.0,  0.4, 5.5),
    "quinoa":          (120,  4.4, 21.0,  1.9, 2.8),
    "pâte":            (131,  5.0, 25.0,  1.1, 1.8),
    "pasta":           (131,  5.0, 25.0,  1.1, 1.8),
    "pain":            (265,  9.0, 49.0,  3.2, 2.7),
    "bread":           (265,  9.0, 49.0,  3.2, 2.7),
    "pomme de terre":  ( 77,  2.0, 17.0,  0.1, 2.2),
    "potato":          ( 77,  2.0, 17.0,  0.1, 2.2),
    "patate":          ( 86,  1.6, 20.0,  0.1, 3.0),
    "brocoli":         ( 34,  2.8,  7.0,  0.4, 2.6),
    "broccoli":        ( 34,  2.8,  7.0,  0.4, 2.6),
    "carotte":         ( 41,  0.9,  9.6,  0.2, 2.8),
    "carrot":          ( 41,  0.9,  9.6,  0.2, 2.8),
    "salade":          ( 15,  1.4,  2.9,  0.2, 1.3),
    "salad":           ( 15,  1.4,  2.9,  0.2, 1.3),
    "tomate":          ( 18,  0.9,  3.9,  0.2, 1.2),
    "tomato":          ( 18,  0.9,  3.9,  0.2, 1.2),
    "fromage":         (402, 25.0,  1.3, 33.0, 0.0),
    "cheese":          (402, 25.0,  1.3, 33.0, 0.0),
    "yaourt":          ( 59,  3.5,  4.7,  3.3, 0.0),
    "yogurt":          ( 59,  3.5,  4.7,  3.3, 0.0),
    "lait":            ( 61,  3.2,  4.8,  3.3, 0.0),
    "milk":            ( 61,  3.2,  4.8,  3.3, 0.0),
    "avocat":          (160,  2.0,  9.0, 15.0, 6.7),
    "avocado":         (160,  2.0,  9.0, 15.0, 6.7),
    "amande":          (579, 21.0, 22.0, 50.0, 12.5),
    "almond":          (579, 21.0, 22.0, 50.0, 12.5),
    "huile":           (884,  0.0,  0.0, 100.0, 0.0),
    "oil":             (884,  0.0,  0.0, 100.0, 0.0),
    "banane":          ( 89,  1.1, 23.0,  0.3, 2.6),
    "banana":          ( 89,  1.1, 23.0,  0.3, 2.6),
    "pomme":           ( 52,  0.3, 14.0,  0.2, 2.4),
    "apple":           ( 52,  0.3, 14.0,  0.2, 2.4),
}
# fmt: on

# Per-100g default for unrecognised foods
_DEFAULT: tuple[float, float, float, float, float] = (150.0, 8.0, 18.0, 5.0, 1.5)

# Assumed serving size in grams for a single detected food item
DEFAULT_SERVING_G: float = 150.0

# Labels that vision models may return which are not food
_NON_FOOD_TOKENS = frozenset(
    {
        "table", "plate", "bowl", "dish", "fork", "knife", "spoon", "glass",
        "cup", "napkin", "background", "menu", "restaurant", "counter",
        "cutting board", "tablecloth", "utensil", "tray",
    }
)


def is_food_label(label: str) -> bool:
    """Return False for labels that are clearly not food items."""
    lower = label.lower()
    return not any(token in lower for token in _NON_FOOD_TOKENS)


class NutritionLookupService:
    """Estimates macronutrients from a list of food names using an embedded table."""

    def lookup(self, food_name: str) -> tuple[tuple[float, float, float, float, float], bool]:
        """Return ``(macros_per_100g, estimated)``.

        *estimated* is ``True`` when the food is not found in the reference table.
        macros_per_100g = (calories, proteins_g, carbs_g, fats_g, fibers_g).
        """
        normalised = food_name.lower().strip()
        for key, macros in _TABLE.items():
            if key in normalised or normalised in key:
                return macros, False
        logger.debug("Food '%s' not in nutrition table — using defaults", food_name)
        return _DEFAULT, True

    def compute_macros(
        self,
        foods: list[str],
        serving_g: float = DEFAULT_SERVING_G,
    ) -> Macros:
        """Aggregate macros for all detected foods.

        Each food is assumed to represent one serving of *serving_g* grams.
        """
        totals = [0.0, 0.0, 0.0, 0.0, 0.0]  # cal, prot, carbs, fat, fiber
        any_estimated = False

        for food in foods:
            per_100g, estimated = self.lookup(food)
            if estimated:
                any_estimated = True
            factor = serving_g / 100.0
            for i, val in enumerate(per_100g):
                totals[i] += val * factor

        return Macros(
            calories=round(totals[0]),
            proteins_g=round(totals[1], 1),
            carbs_g=round(totals[2], 1),
            fats_g=round(totals[3], 1),
            fibers_g=round(totals[4], 1),
            estimated=any_estimated,
        )

    def is_food_label(self, label: str) -> bool:
        """Implement NutritionLookupPort — delegates to the module-level function."""
        return is_food_label(label)

    def get_catalog(self) -> dict[str, tuple[float, float, float, float, float]]:
        """Return the static embedded catalog."""
        return dict(_TABLE)
