"""Клиент для Milvus (векторное хранилище).

Реализует семантический поиск через эмбеддинги.
"""

import logging
import time
from typing import Any

from pymilvus import Collection, connections
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.config.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


def _escape_filter_value(value: str) -> str:
    """Экранирует спецсимволы для Milvus expression."""
    return value.replace("\\", "\\\\").replace("'", "\\'").replace('"', '\\"')


class MilvusClient:
    """Клиент для семантического поиска через Milvus.

    Выполняет поиск по эмбеддингам в векторной базе данных.

    """

    def __init__(
        self,
        embedder: SentenceTransformer | None = None,
        host: str = settings.milvus_host,
        port: int = settings.milvus_port,
        collection_name: str = settings.milvus_collection,
    ) -> None:
        """Инициализация Milvus клиента.

        Args:
            embedder: Опциональная модель эмбеддингов. Если None, загружается.
            host: Хост Milvus.
            port: Порт Milvus.
            collection_name: Имя коллекции.

        """
        logger.info("Инициализация MilvusClient...")

        if embedder is not None:
            self.embedder = embedder
            logger.info("Используется переданная модель эмбеддингов")
        else:
            logger.info("Загрузка модели эмбеддингов: %s", settings.models.embedding)
            self.embedder = SentenceTransformer(settings.models.embedding)

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )
        def _connect():
            logger.info("Подключение к Milvus: %s:%s...", host, port)
            connections.connect("default", host=host, port=port)

        _connect()
        self.collection = Collection(collection_name)
        self.collection.load()

        logger.info("MilvusClient инициализирован")

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = settings.top_k_milvus,
    ) -> list[dict[str, Any]]:
        """Семантический поиск по children через Milvus.

        Args:
            query: Текстовый запрос.
            filters: Опциональные фильтры (например, {"service": "postgres"}).
            top_k: Количество результатов.

        Returns:
            Список найденных документов с метаданными и scores.

        """
        t0 = time.perf_counter()
        query_vector = self.embedder.encode([f"{settings.query_prefix}{query}"])

        expr = ""
        if filters and "service" in filters:
            safe_service = _escape_filter_value(filters["service"])
            expr = f"service == '{safe_service}'"

        results = self.collection.search(
            data=query_vector,
            anns_field="vector",
            param={"metric_type": "COSINE", "params": {"ef": 64}},
            limit=top_k,
            expr=expr,
            output_fields=[
                "text",
                "raw_content",
                "parent_id",
                "chunk_type",
                "source_file",
                "header_path",
                "service",
            ],
        )

        hits = []
        for hit in results[0]:
            hits.append(
                {
                    "doc_id": str(hit.id),
                    "content": hit.entity.get("text"),
                    "raw_content": hit.entity.get("raw_content"),
                    "parent_id": hit.entity.get("parent_id"),
                    "chunk_type": hit.entity.get("chunk_type"),
                    "source": hit.entity.get("source_file"),
                    "path": hit.entity.get("header_path"),
                    "service": hit.entity.get("service"),
                    "score": float(hit.distance),
                }
            )

        duration = time.perf_counter() - t0
        get_metrics_collector().record_search("milvus", duration, len(hits), query, filters)
        return hits

    def get_embedding(self, text: str) -> list[float]:
        """Получает эмбеддинг для текста.

        Args:
            text: Входной текст.

        Returns:
            Вектор эмбеддинга.

        """
        return self.embedder.encode([text])[0].tolist()
