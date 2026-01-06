"""Движок гибридного поиска с Parent-Document Retrieval.

Координирует:
- MilvusClient для семантического поиска
- OpenSearchClient для полнотекстового поиска
- RRF Fusion для объединения результатов
- Cross-Encoder для реранкинга
"""

import asyncio
import logging
from typing import Any

from sentence_transformers import CrossEncoder, SentenceTransformer

from src.config import (
    EMBEDDING_MODEL_NAME,
    FINAL_TOP_K,
    MILVUS_HOST,
    MILVUS_PORT,
    OPENSEARCH_HOST,
    OPENSEARCH_PORT,
    RERANK_MAX_CHARS,
    RERANKER_MODEL_NAME,
    RRF_K,
)
from src.infrastructure.search.milvus_client import MilvusClient
from src.infrastructure.search.opensearch_client import OpenSearchClient

logger = logging.getLogger(__name__)


class SearchEngine:
    """Движок гибридного поиска с Parent-Document Retrieval.

    Ищет по "умным листьям" (children), реранкает их,
    и возвращает "полные ветки" (parents).

    Композирует MilvusClient и OpenSearchClient для гибридного поиска.

    """

    def __init__(
        self,
        embedder: SentenceTransformer | None = None,
        reranker: CrossEncoder | None = None,
        milvus_host: str = MILVUS_HOST,
        milvus_port: str = MILVUS_PORT,
        opensearch_host: str = OPENSEARCH_HOST,
        opensearch_port: int = OPENSEARCH_PORT,
    ) -> None:
        """Инициализирует движок поиска.

        Args:
            embedder: Опциональная модель эмбеддингов.
            reranker: Опциональный реранкер.
            milvus_host: Хост Milvus.
            milvus_port: Порт Milvus.
            opensearch_host: Хост OpenSearch.
            opensearch_port: Порт OpenSearch.

        """
        logger.info("Инициализация SearchEngine...")

        if embedder is not None:
            self.embedder = embedder
            logger.info("Используется переданная модель эмбеддингов")
        else:
            logger.info("Загрузка модели эмбеддингов: %s", EMBEDDING_MODEL_NAME)
            self.embedder = SentenceTransformer(EMBEDDING_MODEL_NAME)

        if reranker is not None:
            self.reranker = reranker
            logger.info("Используется переданная модель реранкера")
        else:
            logger.info("Загрузка модели реранкера: %s", RERANKER_MODEL_NAME)
            self.reranker = CrossEncoder(RERANKER_MODEL_NAME, max_length=512)

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
        """Семантический поиск по children через Milvus."""
        return self.milvus.search(query, filters)

    def search_opensearch(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Полнотекстовый поиск по children через OpenSearch."""
        return self.opensearch.search(query, filters)

    def fetch_parents(self, parent_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Получает parent-документы из OpenSearch DocStore."""
        return self.opensearch.fetch_parents(parent_ids)

    async def retrieve_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
        top_k: int = 20,
    ) -> dict[str, dict[str, Any]]:
        """Получает кандидатов через гибридный поиск БЕЗ реранкинга.

        Выполняет:
        1. Параллельный поиск в Milvus и OpenSearch
        2. RRF-слияние результатов
        3. Получение parent-документов

        Args:
            query: Поисковый запрос.
            filters: Опциональные фильтры.
            top_k: Количество топ-кандидатов.

        Returns:
            Словарь {parent_id: CandidateDoc}.

        """
        tasks = [
            asyncio.to_thread(self.milvus.search, query, filters),
            asyncio.to_thread(self.opensearch.search, query, filters),
        ]

        results = await asyncio.gather(*tasks)
        milvus_hits, opensearch_hits = results[0], results[1]

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
                    "rrf_score": fused_scores[pid],
                    "best_chunk_content": best_chunk_content[pid],
                }

        return candidates

    def rerank_candidates(
        self,
        query: str,
        candidates: dict[str, dict[str, Any]],
        top_k: int = FINAL_TOP_K,
        dedupe_sources: bool = False,
    ) -> list[dict[str, Any]]:
        """Реранкает кандидатов с помощью Cross-Encoder.

        Применяет RERANK_MAX_CHARS для ограничения длины chunk.
        При dedupe_sources=True оставляет только лучший чанк с каждого source.

        Args:
            query: Запрос для реранкинга.
            candidates: Словарь кандидатов от retrieve_candidates.
            top_k: Количество лучших результатов.
            dedupe_sources: Дедупликация по source (один файл = один результат).

        Returns:
            Отсортированный список документов с reranker_score.

        """
        if not candidates:
            return []

        rerank_inputs = []
        pids = []
        for pid, doc in candidates.items():
            chunk_text = doc.get("best_chunk_content", doc.get("content", ""))
            chunk_text = chunk_text[:RERANK_MAX_CHARS]
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
        """Гибридный поиск с Parent-Document Retrieval и RRF.

        Полный пайплайн: retrieve → RRF → fetch parents → rerank.

        Args:
            query: Поисковый запрос.
            filters: Опциональные фильтры.

        Returns:
            Отранжированный список parent-документов.

        """
        candidates = await self.retrieve_candidates(query, filters)
        return self.rerank_candidates(query, candidates)

    def _rrf_fusion(
        self,
        milvus_hits: list[dict[str, Any]],
        opensearch_hits: list[dict[str, Any]],
        k: int = RRF_K,
    ) -> tuple[dict[str, float], dict[str, str]]:
        """Выполняет RRF (Reciprocal Rank Fusion) для объединения результатов.

        Выбирает chunk с лучшим score для каждого parent.

        Args:
            milvus_hits: Результаты из Milvus.
            opensearch_hits: Результаты из OpenSearch.
            k: Константа RRF (по умолчанию RRF_K=60).

        Returns:
            Кортеж (fused_scores, best_chunk_content).

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
