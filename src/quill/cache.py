"""Local response cache to avoid redundant API calls during development."""

import hashlib
import logging
from pathlib import Path

from anthropic.types import Message

__all__ = ["ResponseCache"]

logger = logging.getLogger(__name__)

CACHE_DIR = Path("cache") / "responses"


class ResponseCache:
    """Caches raw Anthropic API responses keyed by a hash of the inputs."""

    def __init__(self, cache_dir: Path = CACHE_DIR) -> None:
        self._dir = cache_dir

    def _key(self, model: str, system: str, text: str) -> str:
        payload = f"{model}\n{system}\n{text}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, model: str, system: str, text: str) -> Message | None:
        """Return a cached Message if one exists, otherwise None."""
        path = self._dir / f"{self._key(model, system, text)}.json"
        if not path.exists():
            return None
        logger.debug("Cache hit: %s", path.name)
        return Message.model_validate_json(path.read_bytes())

    def put(self, model: str, system: str, text: str, response: Message) -> None:
        """Store a raw API response in the cache."""
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._dir / f"{self._key(model, system, text)}.json"
        path.write_text(response.model_dump_json(indent=2))
        logger.debug("Cached response: %s", path.name)
