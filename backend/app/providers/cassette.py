"""Cassette store for record/replay of provider responses.

A cassette is keyed by a hash of the provider, model, prompt version, and canonical request.
Changing a prompt intentionally misses the cache.
"""

import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CassetteStore:
    def __init__(self, root: str) -> None:
        self.root = Path(root)

    @staticmethod
    def make_key(
        provider: str,
        model: str,
        prompt_version: str,
        request: dict[str, Any],
    ) -> str:
        payload = json.dumps(
            {
                "provider": provider,
                "model": model,
                "promptVersion": prompt_version,
                "request": request,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _path(self, provider: str, key: str) -> Path:
        return self.root / provider / f"{key}.json"

    def load(self, provider: str, key: str) -> dict[str, Any] | None:
        path = self._path(provider, key)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def save(
        self,
        provider: str,
        key: str,
        *,
        model: str,
        prompt_version: str,
        request_summary: str,
        response: Any,
    ) -> None:
        path = self._path(provider, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "key": key,
                        "provider": provider,
                        "model": model,
                        "promptVersion": prompt_version,
                        "requestSummary": request_summary,
                        "createdAt": datetime.now(UTC).isoformat(),
                        "response": response,
                    },
                    indent=2,
                )
            )
        except OSError as exc:
            # Recording is a development convenience. A read-only or absent cassette directory
            # (e.g. the production container) must never discard a real provider response.
            logger.warning("Could not write cassette %s: %s", path, exc)
