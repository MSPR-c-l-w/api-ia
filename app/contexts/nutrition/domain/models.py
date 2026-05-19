from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ImbalanceStatus(str, Enum):
    OK = "OK"
    EXCES = "EXCES"
    DEFICIT = "DEFICIT"


class MealStatus(str, Enum):
    EQUILIBRE = "EQUILIBRE"
    DESEQUILIBRE = "DESEQUILIBRE"


@dataclass
class Macros:
    calories: float
    proteins_g: float
    carbs_g: float
    fats_g: float
    fibers_g: float = 0.0
    estimated: bool = False


@dataclass
class NutrientDetail:
    name: str
    actual: float
    target: float
    unit: str
    status: ImbalanceStatus
    deviation_pct: float  # positive = excess, negative = deficit


@dataclass
class HealthProfile:
    """Daily nutritional targets for imbalance detection."""

    daily_calories_target: float = 2000.0
    proteins_target_g: float = 75.0
    carbs_target_g: float = 250.0
    fats_target_g: float = 70.0
    fibers_target_g: float = 25.0


GOAL_PROFILES: dict[str, HealthProfile] = {
    "perte_de_poids": HealthProfile(
        daily_calories_target=1700.0,
        proteins_target_g=90.0,
        carbs_target_g=180.0,
        fats_target_g=55.0,
        fibers_target_g=30.0,
    ),
    "prise_de_masse": HealthProfile(
        daily_calories_target=2700.0,
        proteins_target_g=130.0,
        carbs_target_g=330.0,
        fats_target_g=85.0,
        fibers_target_g=25.0,
    ),
    "equilibre": HealthProfile(),
}
