"""Service d'authentification inter-services vers le backend NestJS.

Obtient et renouvelle automatiquement un JWT access_token en s'authentifiant
avec les credentials d'un compte service définis dans les settings.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Renouveler le token 60 secondes avant expiration (token expire en 900s par défaut)
_RENEWAL_MARGIN_SECONDS = 60


class BackendAuthService:
    """Obtient et met en cache un JWT Bearer token depuis /auth/login."""

    def __init__(
        self,
        backend_url: str,
        email: str,
        password: str,
        timeout_seconds: int = 5,
    ) -> None:
        self._login_url = f"{backend_url.rstrip('/')}/auth/login"
        self._email = email
        self._password = password
        self._timeout = timeout_seconds

        self._token: str | None = None
        self._expires_at: float = 0.0

    def get_token(self) -> str:
        """Retourne un access_token valide (renouvellement automatique)."""
        if self._token and time.time() < self._expires_at - _RENEWAL_MARGIN_SECONDS:
            return self._token
        return self._refresh()

    def _refresh(self) -> str:
        resp = httpx.post(
            self._login_url,
            json={"email": self._email, "password": self._password},
            timeout=self._timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token") or data.get("accessToken", "")
        if not token:
            raise RuntimeError(
                f"BackendAuthService: pas de token dans la réponse: {data}"
            )
        self._token = token
        # JWT expire en ~900s (15 min) par défaut — on suppose 14 min pour la marge
        self._expires_at = time.time() + 840
        logger.info("BackendAuthService: token renouvelé.")
        return token
