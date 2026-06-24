"""Garde-fou de déploiement pour le réentraînement automatique des modèles ML.

Un réentraînement périodique (cf. EtlWeeklySchedulerService côté backend,
équivalent ici via retraining_scheduler.py) ne doit jamais dégrader
silencieusement un modèle déjà en production : on ne remplace le .joblib que
si le nouveau modèle est au moins aussi bon que le précédent sur sa métrique
de référence (F1 ou F1 macro selon le modèle).
"""

from __future__ import annotations

import json
from pathlib import Path


def metrics_path_for(model_path: Path | str) -> Path:
    """Chemin du fichier de métrique associé à un artefact .joblib donné."""
    return Path(model_path).with_suffix(".metrics.json")


def load_previous_metric(model_path: Path | str) -> float | None:
    """Métrique de référence du modèle actuellement déployé, si elle existe."""
    try:
        with open(metrics_path_for(model_path), encoding="utf-8") as f:
            return float(json.load(f)["metric"])
    except (FileNotFoundError, KeyError, ValueError, TypeError):
        return None


def save_metric(model_path: Path | str, metric: float) -> None:
    path = metrics_path_for(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"metric": metric}, f)


def should_deploy(new_metric: float, previous_metric: float | None) -> bool:
    """Déploie si aucun modèle précédent, ou si le nouveau est >= l'ancien.

    L'égalité est acceptée (pas de stricte supériorité) pour permettre un
    réentraînement périodique sur des données plus à jour même sans gain
    mesurable de métrique — l'objectif est d'éviter une dégradation, pas
    d'exiger un progrès à chaque cycle."""
    if previous_metric is None:
        return True
    return new_metric >= previous_metric
