"""Planificateur de réentraînement périodique des modèles ML (sport +
nutrition) — équivalent Python de ``EtlWeeklySchedulerService`` côté backend
(NestJS / ``@nestjs/schedule``), pour ce micro-service Flask/Hypercorn.

Chaque script (``scripts/train_workout_model.py``,
``scripts/train_meal_type_model.py``) est lancé en **sous-processus** plutôt
qu'importé : l'entraînement est lourd (CPU, appels réseau) et ne doit pas
tourner dans le même processus que celui qui sert les requêtes HTTP live.
Le garde-fou de déploiement (``model_deployment_guard``) est appliqué à
l'intérieur de chaque script — ce planificateur ne fait que les déclencher
et journaliser le résultat.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

_scheduler: AsyncIOScheduler | None = None


async def _run_training_script(script_name: str) -> None:
    script_path = _SCRIPTS_DIR / script_name
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(script_path),
        cwd=str(_REPO_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode == 0:
        logger.info(
            "Réentraînement %s terminé avec succès.\n%s",
            script_name,
            stdout.decode(errors="replace"),
        )
    else:
        logger.error(
            "Réentraînement %s a échoué (code %s).\n%s",
            script_name,
            process.returncode,
            stderr.decode(errors="replace"),
        )


async def _retrain_workout() -> None:
    await _run_training_script("train_workout_model.py")


async def _retrain_nutrition() -> None:
    await _run_training_script("train_meal_type_model.py")


def start_scheduler() -> AsyncIOScheduler:
    """Démarre le planificateur hebdomadaire (dimanche nuit). Idempotent :
    un appel répété alors qu'un scheduler tourne déjà ne fait rien."""
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _retrain_workout,
        CronTrigger(day_of_week="sun", hour=3, minute=0),
        id="retrain_workout",
    )
    scheduler.add_job(
        _retrain_nutrition,
        CronTrigger(day_of_week="sun", hour=4, minute=0),
        id="retrain_nutrition",
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Planificateur de réentraînement démarré (hebdomadaire, dimanche).")
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
