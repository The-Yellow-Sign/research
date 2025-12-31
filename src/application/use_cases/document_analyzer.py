"""Use Case: Анализ документов на релевантность.

Отвечает за:
- LLM-анализ отдельного документа
- Параллельный анализ нескольких документов (Context Compression)
- Smart Fallback на reranker score при ошибках LLM
"""

import asyncio
import logging
import math
from typing import Any

from src.config import FINAL_TOP_K, LLM_CONCURRENCY_LIMIT, MIN_RELEVANCE_SCORE
from src.config.metrics import get_metrics_collector
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """Анализатор документов для RAG-пайплайна.

    Выполняет LLM-анализ релевантности документов с поддержкой:
    - Параллельной обработки через asyncio
    - Timeout и fallback на reranker score
    - Context Compression через summary

    """

    def __init__(self, llm: LLMPort) -> None:
        """Инициализация анализатора.

        Args:
            llm: LLM-клиент, реализующий LLMPort.

        """
        self.llm = llm

    async def analyze_single(
        self,
        doc: dict[str, Any],
        query: str,
        doc_index: int,
    ) -> dict[str, Any] | None:
        """Анализирует один документ на релевантность через LLM.

        С timeout 15s и smart fallback на reranker_score.

        Args:
            doc: Документ из результатов поиска.
            query: Запрос пользователя для оценки релевантности.
            doc_index: Индекс документа для логирования.

        Returns:
            Обогащённый документ с summary или None, если ниже порога.

        """
        content = doc.get("raw_content", "")

        try:

            analysis = await asyncio.wait_for(
                self.llm.analyze_document(content, query),
                timeout=30.0,
            )

            if analysis is None:
                raise ValueError("LLM вернул None вместо DocAnalysis")

            logger.debug(
                "Документ %d: score=%d, reasoning=%s",
                doc_index,
                analysis.relevance_score,
                analysis.reasoning[:50] if analysis.reasoning else "",
            )

            if analysis.relevance_score < MIN_RELEVANCE_SCORE:
                logger.info(
                    "Документ %d отфильтрован: score=%d < %d",
                    doc_index,
                    analysis.relevance_score,
                    MIN_RELEVANCE_SCORE,
                )
                return None

            return {
                **doc,
                "raw_content": analysis.summary,
                "original_content": content,
                "relevance_score": analysis.relevance_score,
                "analysis_reasoning": analysis.reasoning,
            }

        except Exception as e:
            error_msg = "Timeout" if isinstance(e, asyncio.TimeoutError) else str(e)
            logger.warning(
                "Документ %d: анализ упал (%s), используем fallback",
                doc_index,
                error_msg,
            )

            return self._apply_fallback(doc, content, doc_index)

    def _apply_fallback(
        self,
        doc: dict[str, Any],
        content: str,
        doc_index: int,
    ) -> dict[str, Any] | None:
        """Применяет fallback на reranker score при ошибке LLM.

        Args:
            doc: Исходный документ.
            content: Содержимое документа.
            doc_index: Индекс документа.

        Returns:
            Документ с fallback-оценкой или None.

        """
        raw_score = doc.get("reranker_score", doc.get("score", 0))
        if isinstance(raw_score, (int, float)):

            normalized = 1 / (1 + math.exp(-float(raw_score)))
        else:
            normalized = 0.5


        fallback_score = int(normalized * 4) + 1
        fallback_score = min(fallback_score, 4)

        if fallback_score < MIN_RELEVANCE_SCORE:
            logger.info(
                "Документ %d (fallback): score=%d < %d, отбрасываем",
                doc_index,
                fallback_score,
                MIN_RELEVANCE_SCORE,
            )
            return None

        return {
            **doc,
            "raw_content": content[:2000],
            "original_content": content,
            "relevance_score": fallback_score,
            "analysis_reasoning": f"[Fallback] reranker_score={raw_score:.2f}→{fallback_score}",
        }

    async def analyze_batch(
        self,
        docs: list[dict[str, Any]],
        query: str,
    ) -> list[dict[str, Any]]:
        """Параллельный анализ документов через asyncio.gather.

        Использует semaphore для ограничения параллельных LLM вызовов.
        Записывает метрики filter rate.

        Args:
            docs: Список документов из поиска.
            query: Запрос для оценки релевантности.

        Returns:
            Отфильтрованные и обогащённые документы, отсортированные по релевантности.

        """
        if not docs:
            return []

        docs_to_analyze = docs[:FINAL_TOP_K]
        logger.info(
            "Анализ %d документов (concurrency=%d)...",
            len(docs_to_analyze), LLM_CONCURRENCY_LIMIT
        )


        semaphore = asyncio.Semaphore(LLM_CONCURRENCY_LIMIT)

        async def analyze_with_limit(doc: dict, idx: int) -> dict | None:
            async with semaphore:
                return await self.analyze_single(doc, query, idx)

        tasks = [
            analyze_with_limit(doc, idx)
            for idx, doc in enumerate(docs_to_analyze, 1)
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        analyzed_docs = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning("Задача анализа %d завершилась с ошибкой: %s", idx, result)
                analyzed_docs.append(docs_to_analyze[idx])
            elif result is not None:
                analyzed_docs.append(result)

        analyzed_docs.sort(
            key=lambda d: d.get("relevance_score", 0),
            reverse=True,
        )

        filtered_count = len(docs_to_analyze) - len(analyzed_docs)
        logger.info(
            "Анализ завершён: %d/%d документов прошли, %d отфильтровано",
            len(analyzed_docs), len(docs_to_analyze), filtered_count
        )


        metrics = get_metrics_collector()
        metrics.record_pipeline_stage(
            "document_analysis",
            0.0,
            total=len(docs_to_analyze),
            passed=len(analyzed_docs),
            filtered=filtered_count,
        )

        return analyzed_docs
