"""Modèle de classification du type de repas appris sur le catalogue Kaggle réel.

Prédit ``meal_type_name`` (Petit-déjeuner / Déjeuner / Dîner / Collation) à
partir des macronutriments d'un aliment. Entraîné sur le vrai catalogue
``Nutrition`` (601+ aliments, label réel du dataset Kaggle — pas une
distillation d'une règle interne), via ``scripts/train_meal_type_model.py``.

Usage prévu : enrichir le classement des aliments par créneau dans
``MealComposerService`` (signal additionnel, pas un remplacement du filtrage
par contraintes/allergies qui reste déterministe).
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from app.contexts.nutrition.domain.meal_type_features import extract_features

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "meal_type_model.joblib"
)

VALID_MEAL_TYPES = ["Petit-déjeuner", "Déjeuner", "Dîner", "Collation"]


class MealTypeModel:
    """Wrapper scikit-learn : entraînement, prédiction, persistance."""

    def __init__(self, learning_rate: float = 0.1, n_estimators: int = 100) -> None:
        self.learning_rate = learning_rate
        self.n_estimators = n_estimators
        self._classifier = GradientBoostingClassifier(
            learning_rate=learning_rate,
            n_estimators=n_estimators,
            max_depth=3,
            random_state=42,
        )
        self._is_fitted = False

    def fit(self, x: np.ndarray, y: list[str]) -> MealTypeModel:
        self._classifier.fit(x, y)
        self._is_fitted = True
        return self

    def predict(self, x: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError(
                "Le modèle n'est pas entraîné (appeler fit() ou load())."
            )
        return self._classifier.predict(x)

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError(
                "Le modèle n'est pas entraîné (appeler fit() ou load())."
            )
        return self._classifier.predict_proba(x)

    def predict_meal_type(self, item: dict) -> str:
        """Prédit le type de repas (Petit-déjeuner/Déjeuner/Dîner/Collation)
        à partir des macros brutes d'un aliment (contrat ``GET /nutrition``)."""
        features = np.array([extract_features(item)])
        return str(self.predict(features)[0])

    def feature_importances(self) -> dict[str, float]:
        if not self._is_fitted:
            raise RuntimeError("Le modèle n'est pas entraîné.")
        from app.contexts.nutrition.domain.meal_type_features import FEATURE_NAMES

        importances = (float(v) for v in self._classifier.feature_importances_)
        return dict(zip(FEATURE_NAMES, importances, strict=True))

    def save(self, path: Path = DEFAULT_MODEL_PATH) -> None:
        if not self._is_fitted:
            raise RuntimeError("Impossible de sauvegarder un modèle non entraîné.")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL_PATH) -> MealTypeModel | None:
        """Retourne None (plutôt que de lever) si le modèle n'existe pas encore."""
        if not path.exists():
            return None
        loaded = joblib.load(path)
        return loaded if isinstance(loaded, cls) else None
