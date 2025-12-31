"""Use Case: Обработка запросов (Query Processor).

Главный оркестратор RAG-пайплайна:
1. Query Expansion
2. Retrieve (Milvus + OpenSearch)
3. Rerank
4. LLM Analysis (Context Compression)
5. Generate Answer
"""

import asyncio
import html
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from src.application.dto.requests import ChatRequest
from src.application.dto.responses import ChatResponse
from src.application.use_cases.document_analyzer import DocumentAnalyzer
from src.application.use_cases.query_expander import QueryExpander
from src.config import FINAL_TOP_K
from src.config.metrics import get_metrics_collector
from src.domain.models.response import SourceDoc
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Главный оркестратор RAG-пайплайна.

    Координирует все этапы обработки запроса:
    - Query Expansion через LLM
    - Гибридный поиск (Milvus + OpenSearch)
    - Context Compression через LLM-анализ
    - Генерация ответа

    """

    def __init__(
        self,
        llm: LLMPort,
        search_engine: Any,
    ) -> None:
        """Инициализация процессора запросов.

        Args:
            llm: LLM-клиент, реализующий LLMPort.
            search_engine: Движок гибридного поиска.

        """
        self.llm = llm
        self.search_engine = search_engine
        self.query_expander = QueryExpander(llm)
        self.document_analyzer = DocumentAnalyzer(llm)

    async def process(self, request: ChatRequest) -> ChatResponse:
        """Обрабатывает запрос через полный RAG-пайплайн.

        Этапы:
        1. Расширение запроса (Query Expansion)
        2. Параллельный гибридный поиск
        3. Объединение и дедупликация результатов
        4. Rerank
        5. LLM-анализ (Context Compression)
        6. Генерация финального ответа

        Args:
            request: ChatRequest с запросом и историей.

        Returns:
            ChatResponse с ответом и источниками.

        """
        timings: dict[str, float] = {}


        t0 = time.perf_counter()
        expansion = await self.query_expander.expand(request.query, request.history)
        queries = self.query_expander.get_all_queries(expansion)
        timings["query_expansion"] = time.perf_counter() - t0


        t0 = time.perf_counter()
        retrieve_tasks = [
            asyncio.to_thread(self.search_engine.retrieve_candidates, q, request.filters)
            for q in queries
        ]
        candidates_list = await asyncio.gather(*retrieve_tasks)
        timings["retrieve"] = time.perf_counter() - t0


        merged_candidates = self._merge_candidates(candidates_list)
        total_candidates = sum(len(c) for c in candidates_list)

        logger.info(
            "Retrieve (%.2fs): %d unique candidates from %d total",
            timings["retrieve"],
            len(merged_candidates),
            total_candidates,
        )


        if not merged_candidates and request.filters:
            logger.info("Нет результатов с фильтром, ищем без фильтра")
            retrieve_tasks = [
                asyncio.to_thread(self.search_engine.retrieve_candidates, q, None)
                for q in queries
            ]
            candidates_list = await asyncio.gather(*retrieve_tasks)
            merged_candidates = self._merge_candidates(candidates_list)

        if not merged_candidates:
            return await self._generate_clarifying_response(
                request.query, expansion.rewritten_query
            )


        t0 = time.perf_counter()
        docs = await asyncio.to_thread(
            self.search_engine.rerank_candidates,
            expansion.rewritten_query,
            merged_candidates,
            FINAL_TOP_K,
        )
        timings["rerank"] = time.perf_counter() - t0

        logger.info(
            "Rerank (%.2fs): top %d from %d candidates",
            timings["rerank"],
            len(docs),
            len(merged_candidates),
        )

        if not docs:
            return await self._generate_clarifying_response(
                request.query, expansion.rewritten_query
            )


        t0 = time.perf_counter()
        analyzed_docs = await self.document_analyzer.analyze_batch(docs, expansion.rewritten_query)
        timings["llm_analysis"] = time.perf_counter() - t0

        logger.info(
            "LLM Analysis (%.2fs): %d/%d документов прошли фильтр",
            timings["llm_analysis"],
            len(analyzed_docs),
            len(docs),
        )

        if not analyzed_docs:
            return await self._generate_clarifying_response(
                request.query, expansion.rewritten_query
            )

        context_xml = self._build_context_xml(analyzed_docs)


        t0 = time.perf_counter()
        answer = await self.llm.generate_answer(context_xml, expansion.rewritten_query)
        timings["llm_generation"] = time.perf_counter() - t0

        logger.info("LLM Generation (%.2fs)", timings["llm_generation"])


        self._record_metrics(timings, request, docs, analyzed_docs, merged_candidates)

        sources = self._build_sources(analyzed_docs)

        return ChatResponse(
            answer_type="final_answer",
            answer=answer,
            sources=sources,
            rewritten_query=expansion.rewritten_query,
        )

    async def process_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming-версия process.

        Yields:
            Токены ответа по мере генерации.

        """
        expansion = await self.query_expander.expand(request.query, request.history)
        queries = self.query_expander.get_all_queries(expansion)


        retrieve_tasks = [
            asyncio.to_thread(self.search_engine.retrieve_candidates, q, request.filters)
            for q in queries
        ]
        candidates_list = await asyncio.gather(*retrieve_tasks)
        merged_candidates = self._merge_candidates(candidates_list)

        if not merged_candidates:
            yield "[NO_RESULTS]"
            return


        docs = await asyncio.to_thread(
            self.search_engine.rerank_candidates,
            expansion.rewritten_query,
            merged_candidates,
            FINAL_TOP_K,
        )

        if not docs:
            yield "[NO_RESULTS]"
            return


        analyzed_docs = await self.document_analyzer.analyze_batch(docs, expansion.rewritten_query)

        if not analyzed_docs:
            yield "[NO_RELEVANT_DOCS]"
            return

        context_xml = self._build_context_xml(analyzed_docs)


        async for token in self.llm.generate_answer_stream(context_xml, expansion.rewritten_query):
            yield token


        sources = self._build_sources(analyzed_docs)
        yield f"\n[SOURCES]{json.dumps([s.model_dump() for s in sources], ensure_ascii=False)}"

    async def _generate_clarifying_response(
        self,
        original_query: str,
        rewritten_query: str,
    ) -> ChatResponse:
        """Генерирует уточняющий вопрос при отсутствии релевантных документов."""
        clarifying_question = await self.llm.generate_clarifying_question(original_query)
        return ChatResponse(
            answer_type="clarifying_question",
            answer=clarifying_question,
            sources=[],
            rewritten_query=rewritten_query,
        )

    def _merge_candidates(
        self,
        candidates_list: list[dict[str, dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        """Объединяет кандидатов с суммированием RRF-скоров."""
        merged: dict[str, dict[str, Any]] = {}

        for candidates in candidates_list:
            for pid, doc in candidates.items():
                if pid in merged:
                    merged[pid]["rrf_score"] += doc.get("rrf_score", 0)
                else:
                    merged[pid] = doc.copy()

        return merged

    def _build_context_xml(self, search_results: list[dict[str, Any]]) -> str:
        """Формирует XML-контекст для LLM."""
        context_parts = ["<documents>"]
        for idx, result in enumerate(search_results, 1):
            relevance = result.get("relevance_score", "N/A")
            safe_content = html.escape(result.get("raw_content", ""))
            safe_service = html.escape(result.get("service", ""))
            safe_source = html.escape(result.get("source", ""))

            context_parts.append(
                f"  <doc id='{idx}' service='{safe_service}' "
                f"source='{safe_source}' relevance='{relevance}'>\n"
                f"{safe_content}\n"
                f"  </doc>"
            )
        context_parts.append("</documents>")
        return "\n".join(context_parts)

    def _build_sources(self, search_results: list[dict[str, Any]]) -> list[SourceDoc]:
        """Конвертирует результаты поиска в DTO источников."""
        sources = []
        for idx, result in enumerate(search_results, 1):
            content = result.get("original_content", result.get("raw_content", ""))
            sources.append(
                SourceDoc(
                    rank=idx,
                    score=result.get("score", 0.0),
                    service=result.get("service", "N/A"),
                    source_file=result.get("source", "N/A"),
                    header_path=result.get("path", ""),
                    content=content,
                )
            )
        return sources

    def _record_metrics(
        self,
        timings: dict[str, float],
        request: ChatRequest,
        docs: list[dict[str, Any]],
        analyzed_docs: list[dict[str, Any]],
        merged_candidates: dict[str, dict[str, Any]],
    ) -> None:
        """Записывает метрики pipeline."""
        total_time = sum(timings.values())
        logger.info(
            "Pipeline: %.2fs | Expand: %.2fs | Retrieve: %.2fs | Rerank: %.2fs | "
            "Analyze: %.2fs | Gen: %.2fs",
            total_time,
            timings.get("query_expansion", 0),
            timings.get("retrieve", 0),
            timings.get("rerank", 0),
            timings.get("llm_analysis", 0),
            timings.get("llm_generation", 0),
        )

        metrics = get_metrics_collector()
        metrics.record_pipeline_stage("query_expansion", timings.get("query_expansion", 0))
        metrics.record_pipeline_stage(
            "retrieve", timings.get("retrieve", 0), hits_count=len(merged_candidates)
        )
        metrics.record_pipeline_stage(
            "rerank", timings.get("rerank", 0), hits_count=len(docs)
        )
        metrics.record_pipeline_stage(
            "llm_analysis", timings.get("llm_analysis", 0),
            docs_in=len(docs), docs_out=len(analyzed_docs)
        )
        metrics.record_pipeline_stage("llm_generation", timings.get("llm_generation", 0))
        metrics.record_request(
            total_duration_sec=total_time,
            docs_retrieved=len(docs),
            docs_filtered=len(docs) - len(analyzed_docs),
            answer_type="final_answer",
            query_preview=request.query,
        )
