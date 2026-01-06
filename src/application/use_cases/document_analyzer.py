"""Use Case: Анализ документов на релевантность.

Отвечает за:
- LLM-реранкинг документов (по образцу RAG-Challenge-2)
- Взвешенное среднее: 0.3×vector + 0.7×llm
- Без жёсткого порога — только сортировка и топ-N
"""

import logging
import math
from typing import Any

from src.config import FINAL_TOP_K, RAG_MODE
from src.config.metrics import get_metrics_collector
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)

VECTOR_WEIGHT = 0.3
LLM_WEIGHT = 0.7

MIN_RELEVANCE_THRESHOLD = 0.3

LLM_FINAL_TOP_K = 5


def normalize_vector_score(score: float) -> float:
    """Нормализует vector/reranker score в диапазон 0-1.

    Использует sigmoid для плавного масштабирования.
    """
    if isinstance(score, (int, float)):
        return 1 / (1 + math.exp(-float(score)))
    return 0.5


class DocumentAnalyzer:
    """Анализатор документов для RAG-пайплайна.

    Использует LLM-реранкинг с взвешенным средним (по образцу RAG-Challenge-2):
    - final_score = 0.3×vector_score + 0.7×llm_score
    - Без жёсткого порога отсечения
    - Сортировка по score, топ-N
    """

    def __init__(self, llm: LLMPort) -> None:
        """Инициализация анализатора.

        Args:
            llm: LLM-клиент, реализующий LLMPort.

        """
        self.llm = llm

    async def analyze_batch(
        self,
        docs: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Реранкинг документов через LLM с взвешенным средним.

        Использует batch reranking для эффективности (3 docs/request).
        Комбинирует vector score и LLM score.

        Args:
            docs: Список документов из поиска.
            query: Запрос для оценки релевантности.

        Returns:
            Отсортированные документы (топ FINAL_TOP_K).

        """
        if not docs:
            return []

        if RAG_MODE == "basic":
            logger.info("Basic mode: skipping LLM reranking")
            return docs[:LLM_FINAL_TOP_K]

        docs_to_analyze = docs[: FINAL_TOP_K * 2]
        logger.info("LLM Reranking %d документов...", len(docs_to_analyze))

        try:
            llm_scores = await self.llm.rerank_batch(query, docs_to_analyze)
        except Exception as e:
            logger.warning("LLM rerank failed, using vector scores only: %s", e)
            llm_scores = [0.5] * len(docs_to_analyze)

        analyzed_docs = []
        for idx, doc in enumerate(docs_to_analyze):
            vector_score = doc.get("reranker_score", doc.get("score", 0))
            normalized_vector = normalize_vector_score(vector_score)

            llm_score = llm_scores[idx] if idx < len(llm_scores) else 0.5

            final_score = VECTOR_WEIGHT * normalized_vector + LLM_WEIGHT * llm_score

            analyzed_docs.append(
                {
                    **doc,
                    "relevance_score": final_score,
                    "llm_score": llm_score,
                    "vector_score_normalized": normalized_vector,
                }
            )

            logger.debug(
                "Doc %d: vector=%.2f, llm=%.2f, final=%.2f",
                idx + 1,
                normalized_vector,
                llm_score,
                final_score,
            )

        analyzed_docs.sort(
            key=lambda d: d.get("relevance_score", 0),
            reverse=True,
        )

        result = analyzed_docs[:LLM_FINAL_TOP_K]

        logger.info(
            "Reranking завершён: топ %d из %d (scores: %.2f - %.2f)",
            len(result),
            len(docs_to_analyze),
            result[0].get("relevance_score", 0) if result else 0,
            result[-1].get("relevance_score", 0) if result else 0,
        )

        max_llm_score = max((d.get("llm_score", 0) for d in result), default=0)
        if max_llm_score < MIN_RELEVANCE_THRESHOLD:
            logger.warning(
                "Низкая релевантность: max_llm_score=%.2f < %.2f",
                max_llm_score,
                MIN_RELEVANCE_THRESHOLD,
            )
            if result:
                result[0]["low_confidence"] = True

        metrics = get_metrics_collector()
        metrics.record_pipeline_stage(
            "document_analysis",
            0.0,
            total=len(docs_to_analyze),
            passed=len(result),
            filtered=len(docs_to_analyze) - len(result),
        )

        return result

    async def analyze_single(
        self,
        doc: dict[str, Any],
        query: str,
        doc_index: int,
    ) -> dict[str, Any] | None:
        """Use analyze_batch instead of this method."""
        logger.warning("analyze_single deprecated, use analyze_batch")
        results = await self.analyze_batch([doc], query)
        return results[0] if results else None
