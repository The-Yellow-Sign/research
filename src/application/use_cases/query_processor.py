"""Use Case: Обработчик запросов (Query Processor).

Главный оркестратор RAG-пайплайна, координирующий все этапы обработки:
1. Query Expansion — расширение и перефразирование запроса
2. Hybrid Retrieve — параллельный поиск в Milvus и OpenSearch
3. RRF Fusion — объединение результатов
4. BGE Rerank — реранжирование через Cross-Encoder
5. LLM Analysis — анализ релевантности и сжатие контекста
6. Generation — генерация финального ответа
"""

import asyncio
import html
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from src.application.dto.requests import ChatRequest
from src.application.dto.responses import ChatResponse, CitationMetrics
from src.application.services.citation_formatter import CitationFootnoteBuilder
from src.application.services.citation_verifier import CitationVerifier
from src.application.use_cases.document_analyzer import DocumentAnalyzer
from src.application.use_cases.query_expander import QueryExpander
from src.config import FINAL_TOP_K, RAG_MODE
from src.config.metrics import get_metrics_collector
from src.domain.models.response import SourceDoc
from src.domain.ports.llm import LLMPort

if TYPE_CHECKING:
    from src.infrastructure.search.engine import SearchEngine

logger = logging.getLogger(__name__)


class QueryProcessor:
    """Главный оркестратор RAG-пайплайна.

    Координирует полный цикл обработки пользовательского запроса:
    от Query Expansion до генерации финального ответа с источниками.

    Attributes:
        llm: LLM-клиент для генерации и анализа.
        search_engine: Движок гибридного поиска.
        query_expander: Компонент расширения запросов.
        document_analyzer: Анализатор релевантности документов.

    """

    def __init__(
        self,
        llm: LLMPort,
        search_engine: "SearchEngine",
    ) -> None:
        """Инициализирует процессор запросов.

        Args:
            llm: LLM-клиент, реализующий интерфейс LLMPort.
            search_engine: Движок гибридного поиска с реранкингом.

        """
        self.llm = llm
        self.search_engine = search_engine
        self.query_expander = QueryExpander(llm)
        self.document_analyzer = DocumentAnalyzer(llm)
        self.citation_verifier = CitationVerifier()
        self.footnote_builder = CitationFootnoteBuilder()

    async def process(self, request: ChatRequest) -> ChatResponse:
        """Обрабатывает запрос через полный RAG-пайплайн.

        Выполняет последовательно все этапы обработки с замером времени.
        При отсутствии релевантных документов генерирует уточняющий вопрос.

        Args:
            request: ChatRequest с запросом пользователя и историей диалога.

        Returns:
            ChatResponse с ответом, источниками и временными метриками.

        """
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        expansion = await self.query_expander.expand(request.query, request.history)
        queries = self.query_expander.get_all_queries(expansion)
        timings["query_expansion"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        retrieve_tasks = [
            self.search_engine.retrieve_candidates(q, request.filters) for q in queries
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
                asyncio.to_thread(self.search_engine.retrieve_candidates, q, None) for q in queries
            ]
            candidates_list = await asyncio.gather(*retrieve_tasks)
            merged_candidates = self._merge_candidates(candidates_list)

        if not merged_candidates:
            return await self._generate_clarifying_response(
                request.query, expansion.rewritten_query
            )

        query_entities = self._extract_keywords_from_variations(expansion.variations)

        t0 = time.perf_counter()
        docs = await asyncio.to_thread(
            self.search_engine.rerank_candidates,
            expansion.rewritten_query,
            merged_candidates,
            FINAL_TOP_K,
            False,
            query_entities,
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

        if RAG_MODE == "full":
            await self._summarize_docs(analyzed_docs)

        if analyzed_docs and analyzed_docs[0].get("low_confidence"):
            logger.warning("Все документы ниже порога релевантности, возвращаем отказ")
            return ChatResponse(
                answer_type="no_relevant_docs",
                answer="В базе знаний отсутствует информация по данному запросу.",
                sources=[],
                rewritten_query=expansion.rewritten_query,
                timings=timings,
            )

        context_xml = self._build_context_xml(analyzed_docs)

        t0 = time.perf_counter()
        answer = await self.llm.generate_answer(context_xml, expansion.rewritten_query)
        timings["llm_generation"] = time.perf_counter() - t0

        logger.info("LLM Generation (%.2fs)", timings["llm_generation"])

        citation_report = self.citation_verifier.verify(answer, len(analyzed_docs))
        if citation_report.invalid_citations:
            logger.warning(
                "Invalid citations detected: %s (valid: 1-%d)",
                citation_report.invalid_citations,
                len(analyzed_docs),
            )
            answer = self.citation_verifier.clean_invalid_citations(
                answer, len(analyzed_docs)
            )

        self._record_metrics(timings, request, docs, analyzed_docs, merged_candidates)

        sources = self._build_sources(analyzed_docs)
        footnotes = self.footnote_builder.build_footnotes(answer, sources)

        citation_metrics = CitationMetrics(
            coverage=citation_report.citation_coverage,
            valid_citations=citation_report.valid_citations,
            invalid_removed=len(citation_report.invalid_citations),
        )

        return ChatResponse(
            answer_type="final_answer",
            answer=answer,
            sources=sources,
            rewritten_query=expansion.rewritten_query,
            timings=timings,
            citation_metrics=citation_metrics,
            footnotes=footnotes,
        )

    async def process_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming-версия обработки запроса.

        Выполняет те же этапы что и process(), но возвращает токены
        ответа по мере их генерации для real-time UI.

        Args:
            request: ChatRequest с запросом пользователя.

        Yields:
            Токены ответа и JSON с источниками в конце.

        """
        expansion = await self.query_expander.expand(request.query, request.history)
        queries = self.query_expander.get_all_queries(expansion)

        retrieve_tasks = [
            self.search_engine.retrieve_candidates(q, request.filters) for q in queries
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

        if RAG_MODE == "full":
            await self._summarize_docs(analyzed_docs)

        if analyzed_docs and analyzed_docs[0].get("low_confidence"):
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
        """Генерирует уточняющий вопрос при отсутствии документов.

        Вызывается когда поиск не нашёл релевантных документов.
        LLM генерирует вопрос для уточнения намерения пользователя.

        Args:
            original_query: Исходный запрос пользователя.
            rewritten_query: Переписанный запрос после Query Expansion.

        Returns:
            ChatResponse с типом clarifying_question.

        """
        clarifying_question = await self.llm.generate_clarifying_question(original_query)
        return ChatResponse(
            answer_type="clarifying_question",
            answer=clarifying_question,
            sources=[],
            rewritten_query=rewritten_query,
        )

    def _extract_keywords_from_variations(
        self,
        variations: list[str],
    ) -> dict[str, list[str]]:
        """Извлекает ключевые слова из результатов Query Expansion.

        Парсит variations[0] (Strict Keywords) для использования
        в Entity Boost при реранкинге. Быстрее отдельного NER.

        Args:
            variations: Список вариаций запроса от Query Expansion.

        Returns:
            Словарь {"keyword": [список ключевых слов]} для Entity Boost.

        """
        if not variations:
            return {}

        strict_keywords = variations[0].lower().split()

        stop_words = {"the", "and", "for", "with", "how", "why", "what"}
        keywords = [kw for kw in strict_keywords if len(kw) >= 3 and kw not in stop_words]

        if keywords:
            logger.debug("Keywords from variations[0]: %s", keywords)
            return {"keyword": keywords}

        return {}

    def _merge_candidates(
        self,
        candidates_list: list[dict[str, dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        """Объединяет кандидатов из нескольких поисковых запросов.

        При пересечении суммирует RRF-скоры для учёта
        множественных подтверждений релевантности.

        Args:
            candidates_list: Результаты параллельных поисковых запросов.

        Returns:
            Объединённый словарь кандидатов с суммарными скорами.

        """
        merged: dict[str, dict[str, Any]] = {}

        for candidates in candidates_list:
            for pid, doc in candidates.items():
                if pid in merged:
                    merged[pid]["rrf_score"] += doc.get("rrf_score", 0)
                else:
                    merged[pid] = doc.copy()

        return merged

    def _build_context_xml(self, search_results: list[dict[str, Any]]) -> str:
        """Формирует XML-контекст для промпта LLM.

        Структурирует документы в XML-формат с экранированием
        специальных символов для безопасной передачи в LLM.

        Args:
            search_results: Список отранжированных документов.

        Returns:
            XML-строка с документами для контекста генерации.

        """
        context_parts = ["<documents>"]
        for idx, result in enumerate(search_results, 1):
            relevance = result.get("relevance_score", "N/A")
            content = result.get("summary_content") or result.get("raw_content", "")
            safe_content = html.escape(content)
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

    async def _summarize_docs(self, docs: list[dict[str, Any]]) -> None:
        """Сжимает документы через LLM (режим full).

        Обновляет поле summary_content in-place для каждого документа.
        Используется только при RAG_MODE="full".

        Args:
            docs: Список документов для сжатия.

        """
        if not docs:
            return

        contents = [doc.get("raw_content", "") for doc in docs]

        summaries = await self.llm.summarize_batch(contents)

        for doc, summary in zip(docs, summaries, strict=False):
            doc["summary_content"] = summary

    def _build_sources(self, search_results: list[dict[str, Any]]) -> list[SourceDoc]:
        """Конвертирует результаты поиска в DTO источников.

        Args:
            search_results: Список документов после анализа.

        Returns:
            Список SourceDoc объектов для включения в ответ.

        """
        sources = []
        for idx, result in enumerate(search_results, 1):
            content = result.get("original_content", result.get("raw_content", ""))
            sources.append(
                SourceDoc(
                    doc_id=idx,
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
        """Записывает метрики выполнения пайплайна.

        Логирует временные метрики и отправляет в MetricsCollector
        для последующего анализа производительности.

        Args:
            timings: Словарь с временами выполнения этапов.
            request: Исходный запрос.
            docs: Документы до фильтрации.
            analyzed_docs: Документы после LLM-фильтрации.
            merged_candidates: Объединённые кандидаты.

        """
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
        metrics.record_pipeline_stage("rerank", timings.get("rerank", 0), hits_count=len(docs))
        metrics.record_pipeline_stage(
            "llm_analysis",
            timings.get("llm_analysis", 0),
            docs_in=len(docs),
            docs_out=len(analyzed_docs),
        )
        metrics.record_pipeline_stage("llm_generation", timings.get("llm_generation", 0))
        metrics.record_request(
            total_duration_sec=total_time,
            docs_retrieved=len(docs),
            docs_filtered=len(docs) - len(analyzed_docs),
            answer_type="final_answer",
            query_preview=request.query,
        )
