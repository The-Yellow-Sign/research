"""Движок гибридного поиска с Parent-Document Retrieval.

Координирует работу компонентов поисковой инфраструктуры:
- MilvusClient для семантического поиска по эмбеддингам
- OpenSearchClient для полнотекстового BM25-поиска
- RRF Fusion для объединения результатов из разных источников
- Cross-Encoder для финального реранкинга кандидатов
"""

import asyncio
import logging
from typing import Any

from sentence_transformers import CrossEncoder, SentenceTransformer

from src.config import settings
from src.infrastructure.search.milvus_client import MilvusClient
from src.infrastructure.search.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)


class SearchEngine:
    """Движок гибридного поиска с Parent-Document Retrieval.

    Реализует двухуровневую архитектуру поиска:
    - Children (чанки): индексируются и ищутся для точного matching
    - Parents (документы): возвращаются пользователю с полным контекстом

    Attributes:
        embedder: Модель для создания векторных эмбеддингов.
        reranker: Cross-encoder для реранкинга кандидатов.
        milvus: Клиент семантического поиска.
        opensearch: Клиент полнотекстового поиска.

    """

    def __init__(
        self,
        embedder: SentenceTransformer | None = None,
        reranker: CrossEncoder | None = None,
        milvus_host: str = settings.milvus_host,
        milvus_port: int = settings.milvus_port,
        opensearch_host: str = settings.opensearch_host,
        opensearch_port: int = settings.opensearch_port,
    ) -> None:
        """Инициализирует движок гибридного поиска.

        При отсутствии переданных моделей загружает модели из конфигурации.
        Создаёт клиенты для Milvus и OpenSearch.

        Args:
            embedder: Предзагруженная модель эмбеддингов (опционально).
            reranker: Предзагруженный cross-encoder (опционально).
            milvus_host: Хост сервера Milvus.
            milvus_port: Порт сервера Milvus.
            opensearch_host: Хост сервера OpenSearch.
            opensearch_port: Порт сервера OpenSearch.

        """
        logger.info("Инициализация SearchEngine...")

        if embedder is not None:
            self.embedder = embedder
            logger.info("Используется переданная модель эмбеддингов")
        else:
            logger.info("Загрузка модели эмбеддингов: %s", settings.models.embedding)
            self.embedder = SentenceTransformer(settings.models.embedding)

        if reranker is not None:
            self.reranker = reranker
            logger.info("Используется переданная модель реранкера")
        else:
            logger.info("Загрузка модели реранкера: %s", settings.models.reranker)
            self.reranker = CrossEncoder(settings.models.reranker, max_length=512)

        self.milvus = MilvusClient(
            embedder=self.embedder,
            host=milvus_host,
            port=milvus_port,
        )
        self.opensearch = OpenSearchClient(
            host=opensearch_host,
            port=opensearch_port,
        )

        self.milvus_collection = self.milvus.collection
        self.opensearch_client = self.opensearch.client

        logger.info("SearchEngine инициализирован")

    def search_milvus(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Выполняет семантический поиск по children-чанкам через Milvus.

        Args:
            query: Поисковый запрос.
            filters: Дополнительные фильтры поиска.

        Returns:
            Список найденных документов с scores.

        """
        return self.milvus.search(query, filters)

    def search_opensearch(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Выполняет полнотекстовый BM25-поиск через OpenSearch.

        Args:
            query: Поисковый запрос.
            filters: Дополнительные фильтры поиска.

        Returns:
            Список найденных документов с BM25 scores.

        """
        return self.opensearch.search(query, filters)

    def fetch_parents(self, parent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Получает parent-документы по идентификаторам.

        Args:
            parent_ids: Список идентификаторов parent-документов.

        Returns:
            Словарь {parent_id: document_data}.

        """
        return self.opensearch.fetch_parents(parent_ids)

    async def retrieve_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """Получает кандидатов через гибридный поиск без реранкинга.

        Выполняет параллельный поиск в Milvus и OpenSearch,
        объединяет результаты через RRF Fusion и загружает
        parent-документы для топ-кандидатов.

        Args:
            query: Поисковый запрос.
            filters: Дополнительные фильтры (service, tags и т.д.).
            top_k: Количество лучших кандидатов для возврата.

        Returns:
            Словарь кандидатов {parent_id: CandidateDoc}.

        """
        milvus_hits = []
        opensearch_hits = []

        async def _safe_milvus():
            nonlocal milvus_hits
            try:
                milvus_hits = await asyncio.to_thread(self.search_milvus, query, filters)
            except Exception as e:
                logger.error("Milvus search failed: %s", e)

        async def _safe_opensearch():
            nonlocal opensearch_hits
            try:
                opensearch_hits = await asyncio.to_thread(self.search_opensearch, query, filters)
            except Exception as e:
                logger.error("OpenSearch search failed: %s", e)

        await asyncio.gather(_safe_milvus(), _safe_opensearch())

        if not milvus_hits and not opensearch_hits:
            logger.warning("Both search backends returned zero results or failed")
            return {}

        fused_scores, best_chunk_content = self._rrf_fusion(milvus_hits, opensearch_hits)

        sorted_pids = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)
        top_pids = [pid for pid, _ in sorted_pids[:top_k]]

        parents = await asyncio.to_thread(self.opensearch.fetch_parents, top_pids)

        candidates = {}
        for pid in top_pids:
            if pid in parents and pid in best_chunk_content:
                candidates[pid] = {
                    "doc_id": pid,
                    "parent_id": pid,
                    "content": parents[pid]["full_text"],
                    "raw_content": parents[pid]["full_text"],
                    "source": parents[pid]["source_file"],
                    "path": parents[pid]["header_path"],
                    "service": parents[pid]["service"],
                    "mentions": parents[pid].get("mentions", {}),
                    "rrf_score": fused_scores[pid],
                    "best_chunk_content": best_chunk_content[pid],
                }

        return candidates

    def rerank_candidates(
        self,
        query: str,
        candidates: dict[str, dict[str, Any]],
        top_k: int = settings.final_top_k,
        dedupe_sources: bool = False,
    ) -> list[dict[str, Any]]:
        """Реранкает кандидатов с помощью Cross-Encoder модели.

        Применяет ограничение RERANK_MAX_CHARS на длину текста чанка
        и опциональную дедупликацию по источникам.

        Args:
            query: Запрос для вычисления релевантности.
            candidates: Словарь кандидатов от retrieve_candidates().
            top_k: Количество лучших результатов для возврата.
            dedupe_sources: Оставить только лучший чанк с каждого источника.

        Returns:
            Отсортированный список документов с reranker_score.

        """
        if not candidates:
            return []

        rerank_inputs = []
        pids = []
        for pid, doc in candidates.items():
            chunk_text = doc.get("best_chunk_content", doc.get("content", ""))
            chunk_text = chunk_text[: settings.rerank_max_chars]
            rerank_inputs.append([query, chunk_text])
            pids.append(pid)

        rerank_scores = self.reranker.predict(rerank_inputs, batch_size=32, show_progress_bar=False)

        results = []
        for pid, score in zip(pids, rerank_scores, strict=True):
            doc = candidates[pid]
            results.append(
                {
                    **doc,
                    "score": float(score),
                    "reranker_score": float(score),
                }
            )

        results.sort(key=lambda x: x["score"], reverse=True)

        if dedupe_sources:
            seen_sources: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for doc in results:
                source = doc.get("metadata", {}).get("source") or doc.get("source", "")
                if source and source not in seen_sources:
                    seen_sources.add(source)
                    deduped.append(doc)
                elif not source:
                    deduped.append(doc)
            results = deduped
            logger.debug("Deduped sources: %d unique from %d total", len(results), len(pids))

        return results[:top_k]

    async def hybrid_search(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Выполняет полный пайплайн гибридного поиска.

        Объединяет все этапы: retrieve → RRF → fetch parents → rerank.

        Args:
            query: Поисковый запрос.
            filters: Дополнительные фильтры поиска.

        Returns:
            Отранжированный список parent-документов.

        """
        candidates = await self.retrieve_candidates(query, filters)
        return self.rerank_candidates(query, candidates)

    def _rrf_fusion(
        self,
        milvus_hits: list[dict[str, Any]],
        opensearch_hits: list[dict[str, Any]],
        k: int = settings.rrf_k,
    ) -> tuple[dict[str, float], dict[str, str]]:
        """Объединяет результаты поиска через Reciprocal Rank Fusion.

        RRF комбинирует ранжирования из разных источников, присваивая
        каждому документу score = sum(1 / (k + rank)) по всем источникам.
        Также выбирает лучший chunk для каждого parent-документа.

        Args:
            milvus_hits: Результаты семантического поиска из Milvus.
            opensearch_hits: Результаты полнотекстового поиска из OpenSearch.
            k: Константа сглаживания RRF (по умолчанию 60).

        Returns:
            Кортеж (fused_scores, best_chunk_content) для каждого parent_id.

        """
        fused_scores: dict[str, float] = {}
        best_chunk_content: dict[str, str] = {}
        best_chunk_scores: dict[str, float] = {}

        def process_hits(hits: list[dict[str, Any]]) -> None:
            for rank, hit in enumerate(hits):
                pid = hit.get("parent_id")
                content = hit.get("content") or hit.get("raw_content") or ""
                hit_score = hit.get("score", 0.0)

                if pid:
                    fused_scores[pid] = fused_scores.get(pid, 0.0) + (1 / (k + rank + 1))
                    if pid not in best_chunk_content or hit_score > best_chunk_scores.get(pid, 0):
                        best_chunk_content[pid] = content
                        best_chunk_scores[pid] = hit_score

        process_hits(milvus_hits)
        process_hits(opensearch_hits)

        return fused_scores, best_chunk_content
