"""Кэш результатов tool calls."""

import hashlib
import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class ToolCallCache:
    """In-memory кэш для результатов инструментов."""

    def __init__(self, ttl_sec: int = 300):
        self._cache: dict[str, tuple[Any, float]] = {}
        self._ttl = ttl_sec

    def _make_key(self, tool_name: str, params: dict) -> str:
        """Генерирует ключ кэша."""
        payload = f"{tool_name}:{json.dumps(params, sort_keys=True)}"
        return hashlib.sha256(payload.encode()).hexdigest()

    def get(self, tool_name: str, params: dict) -> Any | None:
        """Возвращает закэшированный результат или None."""
        key = self._make_key(tool_name, params)
        if key in self._cache:
            result, ts = self._cache[key]
            if time.time() - ts < self._ttl:
                logger.debug("Tool cache hit: %s", tool_name)
                return result
            del self._cache[key]
        return None

    def set(self, tool_name: str, params: dict, result: Any) -> None:
        """Сохраняет результат в кэш."""
        key = self._make_key(tool_name, params)
        self._cache[key] = (result, time.time())

    def clear(self) -> None:
        """Очищает кэш."""
        self._cache.clear()
