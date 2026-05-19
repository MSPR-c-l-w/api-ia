from __future__ import annotations

import json
from urllib import request
from urllib.error import URLError

from app.contexts.nutrition.infrastructure.vision.huggingface_provider import (
    VisionDetection,
)


class GoogleVisionProvider:
    """HTTP adapter for Google Vision (or compatible upstream pipeline endpoint)."""

    def __init__(self, endpoint: str | None, api_key: str | None, timeout_seconds: int = 5) -> None:
        self._endpoint = endpoint
        self._api_key = api_key
        self._timeout = timeout_seconds

    async def detect_foods(
        self,
        image_url: str | None,
        image_base64: str | None,
    ) -> list[VisionDetection]:
        if not self._endpoint:
            return []

        payload = {
            "imageUrl": image_url,
            "imageBase64": image_base64,
        }
        body = json.dumps(payload).encode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self._api_key:
            headers["X-Api-Key"] = self._api_key

        req = request.Request(self._endpoint, data=body, headers=headers, method="POST")
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                content = resp.read().decode("utf-8")
        except (URLError, TimeoutError, OSError):
            return []

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []

        if isinstance(data, dict) and isinstance(data.get("foods"), list):
            detections: list[VisionDetection] = []
            for item in data["foods"]:
                if not isinstance(item, dict):
                    continue
                detections.append(
                    VisionDetection(
                        label=str(item.get("label", "unknown")),
                        confidence=float(item.get("confidence", 0.0)),
                    ),
                )
            return detections

        if isinstance(data, list):
            detections: list[VisionDetection] = []
            for item in data:
                if not isinstance(item, dict):
                    continue
                detections.append(
                    VisionDetection(
                        label=str(item.get("label", "unknown")),
                        confidence=float(item.get("score", 0.0)),
                    ),
                )
            return detections

        return []
