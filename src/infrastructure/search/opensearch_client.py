"""Клиент для OpenSearch (документное хранилище).

Реализует полнотекстовый поиск и хранение документов.
"""

import logging
import time
from typing import Any

from opensearchpy import OpenSearch
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings
from src.config.metrics import get_metrics_collector

logger = logging.getLogger(__name__)


class OpenSearchClient:
    """Клиент для полнотекстового поиска через OpenSearch.

    Выполняет:
    - Полнотекстовый поиск по children
    - Получение parent-документов по ID

    """

    def __init__(
        self,
        host: str = settings.opensearch_host,
        port: int = settings.opensearch_port,
        children_index: str = settings.opensearch_index,
        parent_index: str = settings.opensearch_parent_index,
    ) -> None:
        """Инициализация OpenSearch клиента.

        Args:
            host: Хост OpenSearch.
            port: Порт OpenSearch.
            children_index: Индекс для children-документов.
            parent_index: Индекс для parent-документов.

        """
        logger.info("Инициализация OpenSearchClient...")

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        )
        def _connect():
            logger.info("Подключение к OpenSearch: %s:%s...", host, port)
            return OpenSearch(
                hosts=[{"host": host, "port": port}],
                use_ssl=False,
                pool_maxsize=50,
            )

        self.client = _connect()
        self.children_index = children_index
        self.parent_index = parent_index

        logger.info("OpenSearchClient инициализирован")

    def search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = settings.top_k_opensearch,
    ) -> list[dict[str, Any]]:
        """Полнотекстовый поиск по children через OpenSearch.

        Args:
            query: Текстовый запрос.
            filters: Опциональные фильтры.
            top_k: Количество результатов.

        Returns:
            Список найденных документов с метаданными и scores.

        """
        t0 = time.perf_counter()
        must_clause = {
            "multi_match": {
                "query": query,
                "fields": [
                    "content^2",
                    "content.ngram",
                    "raw_content",
                    "header_path",
                ],
                "type": "best_fields",
            }
        }

        filter_clauses = []
        if filters and "service" in filters:
            filter_clauses.append({"term": {"service": filters["service"]}})

        body = {
            "size": top_k,
            "query": {
                "bool": {
                    "must": must_clause,
                    "filter": filter_clauses,
                }
            },
        }

        response = self.client.search(index=self.children_index, body=body)
        max_score = response["hits"]["max_score"] or 1.0

        hits = []
        for hit in response["hits"]["hits"]:
            source = hit["_source"]
            hits.append(
                {
                    "doc_id": hit["_id"],
                    "content": source.get("content"),
                    "raw_content": source.get("raw_content"),
                    "parent_id": source.get("parent_id"),
                    "chunk_type": source.get("chunk_type"),
                    "source": source.get("source_file"),
                    "path": source.get("header_path"),
                    "service": source.get("service"),
                    "score": hit["_score"] / max_score,
                }
            )

        duration = time.perf_counter() - t0
        get_metrics_collector().record_search("opensearch", duration, len(hits), query, filters)
        return hits

    def fetch_parents(self, parent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Получает parent-документы из OpenSearch DocStore.

        Args:
            parent_ids: Список ID parent-документов.

        Returns:
            Словарь {parent_id: parent_doc}.

        """
        if not parent_ids:
            return {}

        response = self.client.mget(
            index=self.parent_index,
            body={"ids": parent_ids},
        )

        parents = {}
        for doc in response["docs"]:
            if doc.get("found"):
                parent_id = doc["_id"]
                source = doc["_source"]
                parents[parent_id] = {
                    "id": parent_id,
                    "full_text": source.get("full_text", ""),
                    "source_file": source.get("source_file"),
                    "service": source.get("service"),
                    "header_path": source.get("header_path"),
                }

        return parents

    def search_fulltext(
        self,
        query: str,
        top_k: int = settings.top_k_opensearch,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Алиас для search() — совместимость с DocumentStorePort."""
        return self.search(query, filters, top_k)

    def fetch_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Получает документы по списку ID — совместимость с DocumentStorePort."""
        parents = self.fetch_parents(ids)
        return list(parents.values())
