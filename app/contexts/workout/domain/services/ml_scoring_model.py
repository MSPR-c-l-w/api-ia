"""Modèle de scoring appris pour le moteur de recommandation sportif (EPIC #79).

Remplace la formule à poids fixes de ``recommendation_engine.score_exercise``
par un ``GradientBoostingClassifier`` (scikit-learn) entraîné sur des retours
utilisateur (réels + bootstrap synthétique, cf. ``dataset_builder``). Le choix
de Gradient Boosting est motivé par :
  - un hyperparamètre ``learning_rate`` explicite (taux d'apprentissage),
  - une bonne performance sur des features tabulaires peu nombreuses,
  - une robustesse au bruit de label (retours utilisateur subjectifs).

Le modèle est sérialisé sur disque (joblib) ; à l'exécution, si le fichier est
absent (mod conteneur fraîchement démarré, modèle pas encore entraîné), le
moteur retombe sur l'heuristique historique — aucune rupture de service.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier

from app.contexts.workout.domain.services.dataset_builder import Sample
from app.contexts.workout.domain.services.feature_engineering import (
    FEATURE_NAMES,
    extract_features,
)
from app.contexts.workout.domain.value_objects.exercise_definition import (
    ExerciseDefinition,
)
from app.contexts.workout.domain.value_objects.user_profile import UserProfileForScoring

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "exercise_scoring_model.joblib"
)

_SATISFIED_THRESHOLD = 4  # rating >= 4 => exercice "satisfaisant" (label positif)
# Testé à 3 après une première analyse sur un petit échantillon (120
# feedbacks, distribution {2,3,4} sans note 5) qui semblait diluer la classe
# positive. Sur un échantillon plus large (521 feedbacks, distribution
# {2:30, 3:137, 4:211, 5:143}), le seuil à 3 classe 94% des échantillons en
# "satisfaisant" — sur-correction qui rend la tâche triviale (F1 gonflé
# artificiellement). Le seuil à 4 (~68% positif) reste le plus défendable.


def samples_to_xy(samples: list[Sample]) -> tuple[np.ndarray, np.ndarray]:
    """Convertit les triplets (exercice, profil, note) en (X, y) binaire."""
    x = np.array(
        [extract_features(exercise, profile) for exercise, profile, _ in samples],
    )
    y = np.array(
        [1 if rating >= _SATISFIED_THRESHOLD else 0 for _, _, rating in samples],
    )
    return x, y


class ExerciseScoringModel:
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

    def fit(self, x: np.ndarray, y: np.ndarray) -> ExerciseScoringModel:
        self._classifier.fit(x, y)
        self._is_fitted = True
        return self

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError(
                "Le modèle n'est pas entraîné (appeler fit() ou load())."
            )
        return self._classifier.predict_proba(x)[:, 1]

    def predict(self, x: np.ndarray) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError(
                "Le modèle n'est pas entraîné (appeler fit() ou load())."
            )
        return self._classifier.predict(x)

    def score_exercise(
        self,
        exercise: ExerciseDefinition,
        profile: UserProfileForScoring,
    ) -> float:
        """Score 0-1 (probabilité que l'exercice convienne), même contrat que
        l'ancienne heuristique ``recommendation_engine.score_exercise``."""
        features = np.array([extract_features(exercise, profile)])
        return float(self.predict_proba(features)[0])

    def feature_importances(self) -> dict[str, float]:
        if not self._is_fitted:
            raise RuntimeError("Le modèle n'est pas entraîné.")
        importances = (float(v) for v in self._classifier.feature_importances_)
        return dict(zip(FEATURE_NAMES, importances, strict=True))

    def save(self, path: Path = DEFAULT_MODEL_PATH) -> None:
        if not self._is_fitted:
            raise RuntimeError("Impossible de sauvegarder un modèle non entraîné.")
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: Path = DEFAULT_MODEL_PATH) -> ExerciseScoringModel | None:
        """Retourne None (plutôt que de lever) si le modèle n'existe pas encore —
        permet au moteur d'appel de retomber proprement sur l'heuristique."""
        if not path.exists():
            return None
        loaded = joblib.load(path)
        return loaded if isinstance(loaded, cls) else None
