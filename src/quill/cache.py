"""Local response cache to avoid redundant API calls during development."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import orjson

if TYPE_CHECKING:
    from quill.analyzer import AnalysisResult

__all__ = ["ResponseCache"]

logger = logging.getLogger(__name__)

CACHE_DIR = Path.home() / ".cache" / "quill" / "responses"


class ResponseCache:
    """Caches analysis results keyed by a hash of the inputs.

    Args:
        cache_dir: Directory for cached response files.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self._dir = cache_dir

    def _key(self, model: str, system: str, text: str) -> str:
        """Compute a deterministic cache key from model, system prompt, and input text.

        Args:
            model: Model identifier string.
            system: System prompt text.
            text: User input text.

        Returns:
            Hex-encoded SHA-256 hash.
        """
        payload = f"{model}\n{system}\n{text}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, model: str, system: str, text: str) -> AnalysisResult | None:
        """Return a cached AnalysisResult if one exists, otherwise None.

        Args:
            model: Model identifier string.
            system: System prompt text.
            text: User input text.

        Returns:
            Cached AnalysisResult or None on miss / corrupt data.
        """
        from quill.analyzer import AnalysisResult

        path = self._dir / f"{self._key(model, system, text)}.json"
        if not path.exists():
            return None
        try:
            data = orjson.loads(path.read_bytes())
            result = AnalysisResult(**data)
        except Exception:
            logger.warning("Corrupt cache entry %s, treating as miss", path.name)
            return None
        result.cache_hit = True
        logger.debug("Cache hit: %s", path.name)
        return result

    def put(self, model: str, system: str, text: str, result: AnalysisResult) -> None:
        """Store an analysis result in the cache.

        Args:
            model: Model identifier string.
            system: System prompt text.
            text: User input text.
            result: The AnalysisResult to cache.
        """
        from dataclasses import asdict

        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{self._key(model, system, text)}.json"
        data = asdict(result)
        path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))
        logger.debug("Cached response: %s", path.name)
