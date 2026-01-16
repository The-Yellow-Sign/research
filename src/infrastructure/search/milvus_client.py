"""Клиент для Milvus Lite (векторное хранилище).

Реализует семантический поиск через эмбеддинги.
Использует Milvus Lite — embedded режим без отдельного сервера.
"""

import logging
import time
from pathlib import Path
from typing import Any

from pymilvus import MilvusClient as PyMilvusClient
from sentence_transformers import SentenceTransformer

from src.config import (
    EMBEDDING_MODEL_NAME,
    MILVUS_COLLECTION,
    QUERY_PREFIX,
    TOP_K_MILVUS,
)
from src.config.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


MILVUS_LITE_PATH = Path("/workspace/data/milvus_lite.db")


class MilvusClient:
    """Клиент для семантического поиска через Milvus Lite.

    Выполняет поиск по эмбеддингам в локальном файле базы данных.
    Не требует отдельного сервера Milvus.
    """

    def __init__(
        self,
        embedder: SentenceTransformer | None = None,
        db_path: str | Path = MILVUS_LITE_PATH,
        collection_name: str = MILVUS_COLLECTION,
    ) -> None:
        """Инициализация Milvus Lite клиента.

        Args:
            embedder: Опциональная модель эмбеддингов. Если None, загружается.
            db_path: Путь к файлу базы данных Milvus Lite.
            collection_name: Имя коллекции.

        """
        logger.info("Инициализация MilvusClient (Lite mode)...")

        if embedder is not None:
            self.embedder = embedder
            logger.info("Используется переданная модель эмбеддингов")
        else:
            logger.info("Загрузка модели эмбеддингов: %s", EMBEDDING_MODEL_NAME)
            self.embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)


        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)


        self.client = PyMilvusClient(str(db_path))
        self.collection_name = collection_name


        if self.client.has_collection(collection_name):
            logger.info("Коллекция '%s' найдена", collection_name)
        else:
            logger.warning("Коллекция '%s' не найдена. Нужна индексация.", collection_name)

        logger.info("MilvusClient (Lite) инициализирован: %s", db_path)

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = TOP_K_MILVUS,
    ) -> list[dict[str, Any]]:
        """Семантический поиск по children через Milvus Lite.

        Args:
            query: Текстовый запрос.
            filters: Опциональные фильтры (например, {"service": "postgres"}).
            top_k: Количество результатов.

        Returns:
            Список найденных документов с метаданными и scores.

        """
        t0 = time.perf_counter()


        if not self.client.has_collection(self.collection_name):
            logger.warning("Коллекция не существует, возвращаем пустой результат")
            return []

        query_vector = self.embedder.encode([f"{QUERY_PREFIX}{query}"])


        filter_expr = ""
        if filters and "service" in filters:
            filter_expr = f"service == '{filters['service']}'"

        try:
            results = self.client.search(
                collection_name=self.collection_name,
                data=query_vector.tolist(),
                limit=top_k,
                filter=filter_expr if filter_expr else None,
                output_fields=[
                    "text",
                    "raw_content",
                    "parent_id",
                    "chunk_type",
                    "source_file",
                    "header_path",
                    "service",
                ],
                search_params={"metric_type": "COSINE", "params": {"ef": 64}},
            )
        except Exception as e:
            logger.error("Ошибка поиска Milvus Lite: %s", e)
            return []

        hits = []
        for result in results[0] if results else []:
            entity = result.get("entity", {})
            hits.append(
                {
                    "doc_id": str(result.get("id", "")),
                    "content": entity.get("text"),
                    "raw_content": entity.get("raw_content"),
                    "parent_id": entity.get("parent_id"),
                    "chunk_type": entity.get("chunk_type"),
                    "source": entity.get("source_file"),
                    "path": entity.get("header_path"),
                    "service": entity.get("service"),
                    "score": float(result.get("distance", 0.0)),
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

    def create_collection_if_not_exists(
        self,
        dimension: int = 1024,
    ) -> None:
        """Создаёт коллекцию если она не существует.

        Args:
            dimension: Размерность эмбеддингов.

        """
        if self.client.has_collection(self.collection_name):
            logger.info("Коллекция '%s' уже существует", self.collection_name)
            return

        from pymilvus import DataType

        schema = self.client.create_schema(auto_id=True, enable_dynamic_field=True)
        schema.add_field("id", DataType.INT64, is_primary=True)
        schema.add_field("vector", DataType.FLOAT_VECTOR, dim=dimension)
        schema.add_field("text", DataType.VARCHAR, max_length=65535)
        schema.add_field("raw_content", DataType.VARCHAR, max_length=65535)
        schema.add_field("parent_id", DataType.VARCHAR, max_length=255)
        schema.add_field("chunk_type", DataType.VARCHAR, max_length=50)
        schema.add_field("source_file", DataType.VARCHAR, max_length=500)
        schema.add_field("header_path", DataType.VARCHAR, max_length=1000)
        schema.add_field("service", DataType.VARCHAR, max_length=100)

        index_params = self.client.prepare_index_params()
        index_params.add_index(
            field_name="vector",
            metric_type="COSINE",
            index_type="HNSW",
            params={"M": 16, "efConstruction": 200},
        )

        self.client.create_collection(
            collection_name=self.collection_name,
            schema=schema,
            index_params=index_params,
        )
        logger.info("Создана коллекция '%s'", self.collection_name)
