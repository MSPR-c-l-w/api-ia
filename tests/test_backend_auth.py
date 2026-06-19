"""Tests unitaires de BackendAuthService (auth inter-services JWT)."""

from unittest.mock import MagicMock

import httpx
import pytest

from app.contexts.nutrition.infrastructure import backend_auth
from app.contexts.nutrition.infrastructure.backend_auth import BackendAuthService


def _make_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = json_data
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=MagicMock()
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


def test_login_url_is_built_from_backend_url():
    service = BackendAuthService("http://backend:3001/", "svc@x.io", "pw")
    assert service._login_url == "http://backend:3001/auth/login"


def test_refresh_fetches_and_caches_token(monkeypatch):
    calls = []

    def fake_post(url, json, timeout):
        calls.append((url, json, timeout))
        return _make_response({"access_token": "jwt-abc"})

    monkeypatch.setattr(backend_auth.httpx, "post", fake_post)
    service = BackendAuthService("http://backend:3001", "svc@x.io", "pw")

    token = service.get_token()

    assert token == "jwt-abc"
    assert len(calls) == 1
    # Deuxième appel : token toujours valide → pas de nouvel appel HTTP.
    assert service.get_token() == "jwt-abc"
    assert len(calls) == 1


def test_accepts_camelcase_access_token(monkeypatch):
    monkeypatch.setattr(
        backend_auth.httpx,
        "post",
        lambda *a, **k: _make_response({"accessToken": "jwt-camel"}),
    )
    service = BackendAuthService("http://backend:3001", "svc@x.io", "pw")

    assert service.get_token() == "jwt-camel"


def test_raises_when_no_token_in_response(monkeypatch):
    monkeypatch.setattr(
        backend_auth.httpx, "post", lambda *a, **k: _make_response({"foo": "bar"})
    )
    service = BackendAuthService("http://backend:3001", "svc@x.io", "pw")

    with pytest.raises(RuntimeError, match="pas de token"):
        service.get_token()


def test_refreshes_when_token_expired(monkeypatch):
    responses = iter(
        [
            _make_response({"access_token": "first"}),
            _make_response({"access_token": "second"}),
        ]
    )
    monkeypatch.setattr(backend_auth.httpx, "post", lambda *a, **k: next(responses))
    service = BackendAuthService("http://backend:3001", "svc@x.io", "pw")

    assert service.get_token() == "first"
    # Simule l'expiration du token déjà mis en cache.
    service._expires_at = 0.0
    assert service.get_token() == "second"


def test_raises_on_http_error(monkeypatch):
    monkeypatch.setattr(
        backend_auth.httpx,
        "post",
        lambda *a, **k: _make_response({}, status_code=401),
    )
    service = BackendAuthService("http://backend:3001", "svc@x.io", "pw")

    with pytest.raises(httpx.HTTPStatusError):
        service.get_token()
