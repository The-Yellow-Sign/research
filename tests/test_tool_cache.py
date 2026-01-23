"""Tests for ToolCallCache and ObservationManager."""

import time

from src.application.use_cases.observation_manager import ObservationManager
from src.application.use_cases.tool_cache import ToolCallCache


class TestToolCallCache:
    """Тесты для кэша вызовов инструментов."""

    def test_cache_miss_returns_none(self):
        cache = ToolCallCache(ttl_sec=60)
        assert cache.get("tool", {"q": "test"}) is None

    def test_cache_hit_returns_value(self):
        cache = ToolCallCache(ttl_sec=60)
        cache.set("tool", {"q": "test"}, "result")
        assert cache.get("tool", {"q": "test"}) == "result"

    def test_cache_ttl_expiration(self):
        cache = ToolCallCache(ttl_sec=0.1)
        cache.set("tool", {"q": "test"}, "result")
        time.sleep(0.2)
        assert cache.get("tool", {"q": "test"}) is None

    def test_cache_clear(self):
        cache = ToolCallCache(ttl_sec=60)
        cache.set("tool", {"q": "test"}, "result")
        cache.clear()
        assert cache.get("tool", {"q": "test"}) is None

    def test_cache_stores_tuple_with_docs(self):
        """Тест: кэш хранит кортеж (результат, документы)."""
        cache = ToolCallCache(ttl_sec=60)
        cache.set("rag_search", {"q": "test"}, ("result text", [{"id": 1}]))
        result, docs = cache.get("rag_search", {"q": "test"})
        assert result == "result text"
        assert docs == [{"id": 1}]


class TestObservationManager:
    """Тесты для менеджера наблюдений."""

    def test_count_pattern_finds_matches(self):
        obs = ObservationManager(max_tokens=1000)
        obs.add("результатов: 0", priority=2)
        obs.add("результатов: 5", priority=2)
        obs.add("результатов: 0", priority=2)
        assert obs.count_pattern("результатов: 0") == 2

    def test_count_pattern_case_insensitive(self):
        obs = ObservationManager(max_tokens=1000)
        obs.add("ОШИБКА: timeout", priority=3)
        assert obs.count_pattern("ошибка:") == 1
