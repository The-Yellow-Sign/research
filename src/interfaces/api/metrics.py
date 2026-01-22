"""Prometheus metrics для RAG API.

Экспортирует метрики для мониторинга производительности.
"""

import time
from functools import wraps
from typing import Any, Callable

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

REQUESTS_TOTAL = Counter(
    "rag_requests_total",
    "Общее количество запросов RAG",
    ["endpoint", "status"],
)

AGENT_STEPS_TOTAL = Counter(
    "rag_agent_steps_total",
    "Общее количество шагов агента",
    ["action"],
)

TOOL_CALLS_TOTAL = Counter(
    "rag_tool_calls_total",
    "Общее количество вызовов инструментов",
    ["tool_name", "status"],
)


REQUEST_LATENCY = Histogram(
    "rag_request_latency_seconds",
    "Задержка запросов в секундах",
    ["endpoint"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)

AGENT_STEP_LATENCY = Histogram(
    "rag_agent_step_latency_seconds",
    "Задержка шага агента в секундах",
    ["action"],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
)

LLM_LATENCY = Histogram(
    "rag_llm_latency_seconds",
    "Задержка вызова LLM в секундах",
    ["model"],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)


ACTIVE_SESSIONS = Gauge(
    "rag_active_sessions",
    "Количество активных чат-сессий",
)

CACHE_SIZE = Gauge(
    "rag_cache_size",
    "Текущий размер кэша",
    ["cache_type"],
)


def track_request(endpoint: str) -> Callable:
    """Отслеживает метрики запроса с помощью декоратора."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            status = "success"
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                status = "error"
                raise
            finally:
                duration = time.perf_counter() - start
                REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()
                REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)

        return wrapper

    return decorator


def record_agent_step(action: str, duration_sec: float) -> None:
    """Записывает метрики шага агента."""
    AGENT_STEPS_TOTAL.labels(action=action).inc()
    AGENT_STEP_LATENCY.labels(action=action).observe(duration_sec)


def record_tool_call(tool_name: str, success: bool, duration_sec: float) -> None:
    """Записывает метрики вызова инструмента."""
    status = "success" if success else "error"
    TOOL_CALLS_TOTAL.labels(tool_name=tool_name, status=status).inc()


def record_llm_call(model: str, duration_sec: float) -> None:
    """Записывает метрики вызова LLM."""
    LLM_LATENCY.labels(model=model).observe(duration_sec)


def get_metrics() -> bytes:
    """Генерирует выходные данные метрик Prometheus."""
    return generate_latest()


def get_metrics_content_type() -> str:
    """Возвращает тип контента для ответа с метриками."""
    return CONTENT_TYPE_LATEST
