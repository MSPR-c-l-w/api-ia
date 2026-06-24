"""Tests pour le planificateur de réentraînement périodique.

Note : start()/shutdown() d'``AsyncIOScheduler`` sont liés à la boucle
asyncio active au moment de l'appel. Chaque test gère donc son propre cycle
start→assert→shutdown dans la même fonction, plutôt qu'un fixture de
teardown séparé qui pourrait s'exécuter sur une boucle déjà fermée.
"""

from unittest.mock import AsyncMock, patch

from app.shared.infrastructure import retraining_scheduler as rs


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


async def test_run_training_script_logs_success(caplog):
    fake_process = _FakeProcess(returncode=0, stdout=b"ok")
    with (
        patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ),
        caplog.at_level("INFO"),
    ):
        await rs._run_training_script("train_workout_model.py")

    assert "terminé avec succès" in caplog.text


async def test_run_training_script_logs_error_on_failure(caplog):
    fake_process = _FakeProcess(returncode=1, stderr=b"boom")
    with (
        patch(
            "asyncio.create_subprocess_exec",
            AsyncMock(return_value=fake_process),
        ),
        caplog.at_level("ERROR"),
    ):
        await rs._run_training_script("train_meal_type_model.py")

    assert "a échoué" in caplog.text


async def test_start_scheduler_registers_both_jobs_then_shuts_down():
    scheduler = rs.start_scheduler()
    try:
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {"retrain_workout", "retrain_nutrition"}
    finally:
        rs.shutdown_scheduler()


async def test_start_scheduler_is_idempotent_then_shuts_down():
    first = rs.start_scheduler()
    try:
        second = rs.start_scheduler()
        assert first is second
    finally:
        rs.shutdown_scheduler()


async def test_shutdown_then_start_creates_a_fresh_scheduler():
    first = rs.start_scheduler()
    rs.shutdown_scheduler()
    second = rs.start_scheduler()
    try:
        assert first is not second
    finally:
        rs.shutdown_scheduler()
