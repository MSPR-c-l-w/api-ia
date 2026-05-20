"""In-memory AI result cache with TTL (#91).

Avoids redundant calls to vision APIs and LLM for identical inputs.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class AiCacheService:
    """Thread-safe in-memory key/value cache with per-entry TTL.

    Uses threading.Lock for synchronization to ensure safe access from
    multiple concurrent requests in async/ASGI environments.
    Cache keys are derived from content hashes so callers never have to
    manage key construction themselves.
    """

    def __init__(self) -> None:
        self._store: dict[str, tuple[Any, float]] = {}
        self._hits = 0
        self._misses = 0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Low-level get/set
    # ------------------------------------------------------------------

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                self._misses += 1
                return None
            self._hits += 1
            logger.debug("Cache HIT  key=%s", key)
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        with self._lock:
            self._store[key] = (value, time.monotonic() + ttl_seconds)
            logger.debug("Cache SET  key=%s  ttl=%ds", key, ttl_seconds)

    # ------------------------------------------------------------------
    # Semantic key builders
    # ------------------------------------------------------------------

    def image_key(self, image_url: str | None, image_base64: str | None) -> str:
        """Stable key for a vision detection request."""
        return self._hash_key("img", {"url": image_url, "b64_len": len(image_base64 or "")})

    def llm_key(self, goal: str, imbalance_tokens: list[str]) -> str:
        """Stable key for an LLM suggestion request."""
        return self._hash_key("llm", {"goal": goal, "imbalances": sorted(imbalance_tokens)})

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict[str, int]:
        with self._lock:
            return {"hits": self._hits, "misses": self._misses}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_key(prefix: str, data: dict) -> str:
        raw = json.dumps(data, sort_keys=True)
        digest = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return f"{prefix}:{digest}"
