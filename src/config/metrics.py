"""Модуль сбора метрик RAG-пайплайна.

Собирает метрики локально с возможностью лёгкой миграции на OTLP/Prometheus.
Хранение: JSON-файлы в volumes/metrics/.
"""

import atexit
import json
import logging
import threading
from collections import deque
from datetime import datetime
from typing import Any

from src.config.settings import settings

logger = logging.getLogger(__name__)
METRICS_DIR = settings.project_root / "volumes" / "metrics"


class MetricsCollector:
    """Коллектор метрик RAG-пайплайна.

    Собирает метрики в память и периодически сбрасывает в JSON.
    Потокобезопасен.

    Пример использования:
        metrics = get_metrics_collector()
        metrics.record_llm_call("expand_query", 0.8, 150, 50, "qwen")
        metrics.record_search("milvus", 0.15, 25, "как настроить nginx")

    """

    FLUSH_THRESHOLD = 100
    QUERY_PREVIEW_LIMIT = 100

    _instance: "MetricsCollector | None" = None
    _lock = threading.Lock()

    def __new__(cls) -> "MetricsCollector":
        """Singleton паттерн для глобального коллектора."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Инициализирует коллектор метрик."""
        if self._initialized:
            return

        self._buffer: deque[dict[str, Any]] = deque(maxlen=settings.metrics_buffer_size)
        self._buffer_lock = threading.Lock()
        self._initialized = True

        METRICS_DIR.mkdir(parents=True, exist_ok=True)

        atexit.register(self.flush_to_disk)

        logger.info("MetricsCollector инициализирован, директория: %s", METRICS_DIR)

    def _record(self, metric_type: str, data: dict[str, Any]) -> None:
        """Записывает метрику в буфер."""
        record = {
            "timestamp": datetime.now().isoformat(),
            "type": metric_type,
            **data,
        }
        should_flush = False
        with self._buffer_lock:
            self._buffer.append(record)
            if len(self._buffer) >= self.FLUSH_THRESHOLD:
                should_flush = True

        if should_flush:
            self._async_flush()

    def _async_flush(self) -> None:
        """Асинхронный flush в отдельном потоке."""
        thread = threading.Thread(target=self.flush_to_disk, daemon=True)
        thread.start()

    def record_llm_call(
        self,
        operation: str,
        duration_sec: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        model: str = "",
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Записывает метрику LLM-вызова.

        Args:
            operation: Название операции (expand_query, analyze_document, generate_answer).
            duration_sec: Время выполнения в секундах.
            tokens_in: Количество входных токенов (примерно).
            tokens_out: Количество выходных токенов (примерно).
            model: Название модели.
            success: Успешно ли выполнено.
            error: Текст ошибки, если есть.

        """
        self._record(
            "llm_call",
            {
                "operation": operation,
                "duration_sec": round(duration_sec, 4),
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "model": model,
                "success": success,
                "error": error,
            },
        )
        if success:
            try:
                from src.interfaces.api.metrics import record_llm_call

                record_llm_call(model, duration_sec)
            except Exception as e:
                logger.debug("Failed to record LLM call metric: %s", e)

    def record_search(
        self,
        engine: str,
        duration_sec: float,
        hits_count: int,
        query: str = "",
        filters: dict[str, Any] | None = None,
    ) -> None:
        """Записывает метрику поисковой операции.

        Args:
            engine: Движок поиска (milvus, opensearch).
            duration_sec: Время выполнения в секундах.
            hits_count: Количество найденных документов.
            query: Текст запроса (для анализа).
            filters: Примененные фильтры.

        """
        self._record(
            "search",
            {
                "engine": engine,
                "duration_sec": round(duration_sec, 4),
                "hits_count": hits_count,
                "query_preview": query[: self.QUERY_PREVIEW_LIMIT] if query else "",
                "has_filters": bool(filters),
            },
        )

    def record_pipeline_stage(
        self,
        stage: str,
        duration_sec: float,
        **extra: Any,
    ) -> None:
        """Записывает метрику этапа пайплайна.

        Args:
            stage: Название этапа (query_expansion, hybrid_search, llm_analysis, generation).
            duration_sec: Время выполнения в секундах.
            **extra: Дополнительные данные.

        """
        self._record(
            "pipeline_stage",
            {
                "stage": stage,
                "duration_sec": round(duration_sec, 4),
                **extra,
            },
        )

    def record_request(
        self,
        total_duration_sec: float,
        docs_retrieved: int,
        docs_filtered: int,
        answer_type: str,
        query_preview: str = "",
    ) -> None:
        """Записывает метрику полного запроса.

        Args:
            total_duration_sec: Общее время обработки.
            docs_retrieved: Количество найденных документов.
            docs_filtered: Количество отфильтрованных документов.
            answer_type: Тип ответа (final_answer, clarifying_question).
            query_preview: Превью запроса.

        """
        self._record(
            "request",
            {
                "total_duration_sec": round(total_duration_sec, 4),
                "docs_retrieved": docs_retrieved,
                "docs_filtered": docs_filtered,
                "answer_type": answer_type,
                "query_preview": query_preview[: self.QUERY_PREVIEW_LIMIT] if query_preview else "",
            },
        )

    def flush_to_disk(self) -> None:
        """Сбрасывает буфер в JSON-файл."""
        with self._buffer_lock:
            if not self._buffer:
                return
            records = list(self._buffer)
            self._buffer.clear()

        if not records:
            return

        today = datetime.now().strftime("%Y-%m-%d")
        filepath = METRICS_DIR / f"metrics_{today}.jsonl"

        try:
            with filepath.open("a", encoding="utf-8") as f:
                for record in records:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug("Записано %d метрик в %s", len(records), filepath)
        except Exception as e:
            logger.error("Ошибка записи метрик: %s", e)

    def get_summary(self, last_n: int = 100) -> dict[str, Any]:
        """Возвращает сводку по последним метрикам.

        Args:
            last_n: Количество последних записей для анализа.

        Returns:
            Словарь со сводными метриками.

        """
        with self._buffer_lock:
            records = list(self._buffer)[-last_n:]

        if not records:
            return {"message": "Нет метрик в буфере"}

        llm_calls = [r for r in records if r["type"] == "llm_call"]
        searches = [r for r in records if r["type"] == "search"]
        requests = [r for r in records if r["type"] == "request"]

        def avg(lst: list, key: str) -> float:
            vals = [r.get(key, 0) for r in lst]
            return round(sum(vals) / len(vals), 4) if vals else 0

        return {
            "total_records": len(records),
            "llm": {
                "count": len(llm_calls),
                "avg_duration_sec": avg(llm_calls, "duration_sec"),
                "total_tokens_in": sum(r.get("tokens_in", 0) for r in llm_calls),
                "total_tokens_out": sum(r.get("tokens_out", 0) for r in llm_calls),
                "error_rate": (
                    sum(1 for r in llm_calls if not r.get("success", True)) / len(llm_calls)
                    if llm_calls
                    else 0
                ),
            },
            "search": {
                "count": len(searches),
                "avg_duration_sec": avg(searches, "duration_sec"),
                "avg_hits": avg(searches, "hits_count"),
            },
            "requests": {
                "count": len(requests),
                "avg_duration_sec": avg(requests, "total_duration_sec"),
                "by_answer_type": {
                    t: sum(1 for r in requests if r.get("answer_type") == t)
                    for t in {"final_answer", "clarifying_question"}
                },
            },
        }

    def get_buffer_size(self) -> int:
        """Возвращает текущий размер буфера."""
        with self._buffer_lock:
            return len(self._buffer)


def get_metrics_collector() -> MetricsCollector:
    """Возвращает глобальный экземпляр MetricsCollector."""
    return MetricsCollector()
