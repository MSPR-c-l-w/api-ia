"""Tests pour le garde-fou de déploiement des modèles réentraînés."""

from app.shared.domain.model_deployment_guard import (
    load_previous_metric,
    save_metric,
    should_deploy,
)


def test_load_previous_metric_returns_none_when_no_file(tmp_path):
    model_path = tmp_path / "model.joblib"
    assert load_previous_metric(model_path) is None


def test_save_and_load_metric_roundtrip(tmp_path):
    model_path = tmp_path / "model.joblib"
    save_metric(model_path, 0.7958)

    assert load_previous_metric(model_path) == 0.7958


def test_metrics_file_is_a_sidecar_next_to_the_model(tmp_path):
    model_path = tmp_path / "model.joblib"
    save_metric(model_path, 0.5)

    assert (tmp_path / "model.metrics.json").exists()
    assert not model_path.exists()  # le garde-fou ne touche pas au .joblib


def test_should_deploy_when_no_previous_metric():
    assert should_deploy(new_metric=0.1, previous_metric=None) is True


def test_should_deploy_when_new_metric_is_better():
    assert should_deploy(new_metric=0.8, previous_metric=0.7) is True


def test_should_deploy_when_new_metric_is_equal():
    assert should_deploy(new_metric=0.7, previous_metric=0.7) is True


def test_should_not_deploy_when_new_metric_is_worse():
    assert should_deploy(new_metric=0.6, previous_metric=0.7) is False


def test_load_previous_metric_returns_none_on_corrupted_file(tmp_path):
    model_path = tmp_path / "model.joblib"
    metrics_path = tmp_path / "model.metrics.json"
    metrics_path.write_text("not valid json", encoding="utf-8")

    assert load_previous_metric(model_path) is None
