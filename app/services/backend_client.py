"""
HTTP client that fetches real user data from the NestJS backend.

Endpoints consumed:
  GET /auth/me                 → User (date_of_birth, gender, height)
  GET /health-profile/me       → HealthProfile (weight, bmi, activity_level, daily_calories_target)
  GET /nutrition?page=&limit=  → paginated Nutrition catalogue
"""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import requests
from flask import current_app


class BackendError(Exception):
    """Raised when the backend returns an unexpected response."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    return current_app.config["BACKEND_URL"].rstrip("/")


def _headers(jwt_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {jwt_token}"}


def _get(path: str, jwt_token: str, params: dict | None = None) -> Any:
    """Perform an authenticated GET against the NestJS backend."""
    url = f"{_base_url()}{path}"
    try:
        resp = requests.get(
            url,
            headers=_headers(jwt_token),
            params=params,
            timeout=current_app.config.get("BACKEND_TIMEOUT", 10),
        )
    except requests.exceptions.ConnectionError as exc:
        raise BackendError(f"Backend unreachable at {url}: {exc}", 503) from exc
    except requests.exceptions.Timeout as exc:
        raise BackendError(f"Backend timed out at {url}", 504) from exc

    if resp.status_code == 401:
        raise BackendError("Invalid or expired JWT token", 401)
    if resp.status_code == 404:
        raise BackendError(f"Resource not found: {path}", 404)
    if not resp.ok:
        raise BackendError(
            f"Backend returned {resp.status_code} for {path}: {resp.text[:200]}",
            resp.status_code,
        )

    return resp.json()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def fetch_user_profile(jwt_token: str) -> dict[str, Any]:
    """
    Return the authenticated user's profile from GET /auth/me.

    Normalises the response to a flat dict with:
        first_name, last_name, date_of_birth, gender, height
    """
    return _get("/auth/me", jwt_token)


def fetch_health_profile(jwt_token: str) -> dict[str, Any]:
    """
    Return the authenticated user's health profile from GET /health-profile/me.

    Keys: weight, bmi, physical_activity_level, daily_calories_target
    """
    return _get("/health-profile/me", jwt_token)


def fetch_nutrition_catalogue(
    jwt_token: str, limit: int = 100
) -> list[dict[str, Any]]:
    """
    Fetch the full nutrition catalogue from GET /nutrition, handling pagination.

    Returns a flat list of Nutrition objects.
    """
    # First request to know total
    first = _get("/nutrition", jwt_token, params={"page": 1, "limit": limit})

    # Backend returns { data: [...], total: N }
    if isinstance(first, dict) and "data" in first:
        items: list[dict] = list(first["data"])
        total: int = first.get("total", len(items))
        total_pages = math.ceil(total / limit)

        for page in range(2, total_pages + 1):
            page_data = _get("/nutrition", jwt_token, params={"page": page, "limit": limit})
            items.extend(page_data.get("data", []))

        return items

    # Fallback: backend returned a plain list
    return list(first)


def normalise_activity_level(raw: str | None) -> str:
    """
    Normalise activity level from backend values to model-expected values.
    Backend may store English labels ('Moderate', 'Active', 'Sedentary', etc.)
    or already-normalised values.
    """
    if not raw:
        return "moderately_active"
    val = raw.strip().lower().replace(" ", "_").replace("-", "_")
    _map = {
        "sedentary": "sedentary",
        "lightly_active": "lightly_active",
        "light": "lightly_active",
        "low": "lightly_active",
        "moderate": "moderately_active",
        "moderately_active": "moderately_active",
        "medium": "moderately_active",
        "active": "very_active",
        "very_active": "very_active",
        "high": "very_active",
        "extra_active": "extra_active",
        "extremely_active": "extra_active",
        "very_high": "extra_active",
    }
    return _map.get(val, "moderately_active")


def normalise_gender(raw: str | None) -> str:
    """
    Normalise a gender string from the backend to 'male' or 'female'.
    The backend stores French values ('Homme', 'Femme', 'Non spécifié').
    """
    if not raw:
        return "male"
    val = raw.strip().lower()
    if val in {"homme", "male", "m", "man"}:
        return "male"
    if val in {"femme", "female", "f", "woman"}:
        return "female"
    return "male"  # default for 'Non spécifié' etc.


def compute_age(date_of_birth: str | None) -> int | None:
    """Convert an ISO date string to an age in years. Returns None if missing."""
    if not date_of_birth:
        return None
    try:
        dob = datetime.fromisoformat(date_of_birth.replace("Z", "+00:00")).date()
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    except (ValueError, AttributeError):
        return None
