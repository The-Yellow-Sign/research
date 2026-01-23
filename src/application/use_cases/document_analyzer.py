"""Use Case: Анализатор документов для RAG-пайплайна.

Реализует LLM-реранкинг документов.
Использует взвешенное среднее vector и LLM scores для финального ранжирования.
"""

import asyncio
import logging
import math
from typing import Any

from src.application.prompts.registry import PromptRegistry
from src.config import settings
from src.config.metrics import get_metrics_collector
from src.domain.models.query import RerankerBatchResult, RerankerResult
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


def normalize_vector_score(score: float) -> float:
    """Нормализует vector/reranker score в диапазон 0-1.

    Применяет sigmoid-функцию для плавного масштабирования
    произвольных значений score в вероятностный диапазон.
    """
    if isinstance(score, (int, float)):
        return 1 / (1 + math.exp(-float(score)))
    return 0.5


class DocumentAnalyzer:
    """Анализатор документов с LLM-реранкингом.

    Комбинирует vector score от BGE Cross-Encoder с LLM-оценкой
    релевантности для более точного ранжирования документов.

    Формула: final_score = 0.3 × vector_score + 0.7 × llm_score
    """

    def __init__(self, llm: LLMPort) -> None:
        """Инициализирует анализатор документов.

        Args:
            llm: LLM-клиент, реализующий интерфейс LLMPort.

        """
        self.llm = llm
        self._prompt_registry = PromptRegistry()

        # Determine model to use (can be different from main LLM)
        self.reranking_model = settings.models.reranker

    async def analyze_batch(
        self,
        docs: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Выполняет LLM-реранкинг документов.

        Применяет batch reranking через LLM для эффективной оценки.
        Комбинирует vector и LLM scores с весами VECTOR_WEIGHT/LLM_WEIGHT.
        Фильтрует документы с llm_score < 0.2.
        """
        if not docs:
            return []

        if not settings.use_llm_reranking:
            logger.info("Basic mode: skipping LLM reranking")
            return docs[: settings.final_top_k]

        docs_to_analyze = docs[: settings.final_top_k * 2]
        logger.info("LLM Reranking %d документов...", len(docs_to_analyze))

        try:
            llm_scores = await self.rerank_batch(query, docs_to_analyze)
        except Exception as e:
            logger.warning("LLM rerank failed, using vector scores only: %s", e)
            llm_scores = [0.5] * len(docs_to_analyze)

        analyzed_docs = []
        for idx, doc in enumerate(docs_to_analyze):
            vector_score = doc.get("reranker_score", doc.get("score", 0))
            normalized_vector = normalize_vector_score(vector_score)

            llm_score = llm_scores[idx] if idx < len(llm_scores) else 0.5

            final_score = (
                settings.vector_weight * normalized_vector + settings.llm_rerank_weight * llm_score
            )

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

        filtered_docs = [d for d in analyzed_docs if d.get("llm_score", 0) >= 0.2]
        result = filtered_docs[: settings.llm_final_top_k]

        logger.info(
            "Reranking завершён: топ %d из %d (scores: %.2f - %.2f)",
            len(result),
            len(docs_to_analyze),
            result[0].get("relevance_score", 0) if result else 0,
            result[-1].get("relevance_score", 0) if result else 0,
        )

        max_llm_score = max((d.get("llm_score", 0) for d in result), default=0)
        if max_llm_score < settings.min_relevance_threshold:
            logger.warning(
                "Низкая релевантность: max_llm_score=%.2f < %.2f",
                max_llm_score,
                settings.min_relevance_threshold,
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

    async def rerank_batch(
        self,
        query: str,
        documents: list[dict],
        batch_size: int = 5,
    ) -> list[float]:
        """Реранкинг документов через LLM.

        Оценивает документы батчами для эффективности.
        """
        scores = []
        batches = [documents[i : i + batch_size] for i in range(0, len(documents), batch_size)]

        tasks = [self._process_batch_rerank(query, batch) for batch in batches]
        results = await asyncio.gather(*tasks)

        for batch_res in results:
            scores.extend(batch_res)

        return scores

    async def _process_batch_rerank(self, query: str, batch_docs: list[dict]) -> list[float]:
        """Обрабатывает один батч документов для реранкинга."""
        batch_scores = []

        # This was previously in LLMClient, now moved here (Service Layer)

        if len(batch_docs) == 1:
            content = batch_docs[0].get("raw_content", "")[: settings.rerank_max_chars]
            prompt = (
                f"{self._prompt_registry.get('reranker_prompt_single')}\n\n"
                f"Query: {query}\n\nDocument:\n---\n{content}\n---"
            )

            try:
                # Use generic generate_structured
                result = await self.llm.generate_structured(
                    messages=[{"role": "user", "content": prompt}],
                    response_model=RerankerResult,
                    max_tokens=300,
                    temperature=0.0
                )
                batch_scores.append(result.relevance_score if result else 0.5)
            except Exception as e:
                logger.warning("Rerank single error: %s", e)
                batch_scores.append(0.5)
        else:
            blocks_text = ""
            for idx, doc in enumerate(batch_docs, 1):
                content = doc.get("raw_content", "")[: settings.rerank_max_chars]
                blocks_text += f"\n[Block {idx}]:\n{content}\n"

            prompt = (
                f"{self._prompt_registry.get('reranker_prompt_batch')}\n\n"
                f"Query: {query}\n{blocks_text}"
            )

            try:
                result = await self.llm.generate_structured(
                    messages=[{"role": "user", "content": prompt}],
                    response_model=RerankerBatchResult,
                    max_tokens=500,
                    temperature=0.0
                )

                if result and result.block_rankings:
                    for ranking in result.block_rankings[: len(batch_docs)]:
                        batch_scores.append(ranking.relevance_score)
                    while len(batch_scores) < len(batch_docs):
                        batch_scores.append(0.5)
                else:
                    batch_scores.extend([0.5] * len(batch_docs))
            except Exception as e:
                logger.warning("Rerank batch error: %s", e)
                batch_scores.extend([0.5] * len(batch_docs))

        return batch_scores
