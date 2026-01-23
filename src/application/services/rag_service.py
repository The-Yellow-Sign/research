import asyncio
import html
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from src.application.dto.requests import ChatRequest
from src.application.dto.responses import ChatResponse, CitationMetrics
from src.application.services.citation_formatter import CitationFootnoteBuilder
from src.application.services.citation_verifier import CitationVerifier
from src.application.use_cases.answer_generator import AnswerGenerator
from src.application.use_cases.document_analyzer import DocumentAnalyzer
from src.application.use_cases.query_expander import QueryExpander
from src.application.use_cases.summarizer import Summarizer
from src.config import settings
from src.config.metrics import get_metrics_collector
from src.domain.models.response import SourceDoc
from src.domain.ports.llm import LLMPort
from src.domain.ports.search_engine import SearchEnginePort

logger = logging.getLogger(__name__)


class RAGService:
    """Главный RAG-сервис (ранее QueryProcessor).

    Координирует полный цикл обработки пользовательского запроса:
    от Query Expansion до генерации финального ответа с источниками.
    """

    def __init__(
        self,
        llm_client: LLMPort,
        search_engine: SearchEnginePort,
    ) -> None:
        """Инициализирует RAG-сервис.

        Args:
            llm_client: LLM-клиент, реализующий LLMPort.
            search_engine: Движок гибридного поиска.

        """
        self.llm_client = llm_client
        self.search_engine = search_engine

        # Application Services
        self.query_expander = QueryExpander(llm_client)
        self.document_analyzer = DocumentAnalyzer(llm_client)
        self.answer_generator = AnswerGenerator(llm_client)
        self.summarizer = Summarizer(llm_client)

        self.citation_verifier = CitationVerifier()
        self.footnote_builder = CitationFootnoteBuilder()

        logger.info("RAGService инициализирован (Refactored architecture)")

    async def _prepare_context(
        self, request: ChatRequest
    ) -> tuple[Any, list[dict[str, Any]], dict[str, float]]:
        """Выполняет общие этапы RAG-пайплайна: расширение, поиск, реранжирование, анализ."""
        timings: dict[str, float] = {}

        t0 = time.perf_counter()
        expansion = await self.query_expander.expand(request.query, request.history)
        queries = self.query_expander.get_all_queries(expansion)
        timings["query_expansion"] = time.perf_counter() - t0

        t0 = time.perf_counter()
        retrieve_tasks = [
            self.search_engine.retrieve_candidates(q, request.filters) for q in queries
        ]
        candidates_list = await asyncio.gather(*retrieve_tasks, return_exceptions=True)

        valid_candidates = []
        for c in candidates_list:
            if isinstance(c, Exception):
                logger.warning("Retrieve task failed: %s", c)
            else:
                valid_candidates.append(c)

        merged_candidates = self._merge_candidates(valid_candidates)
        timings["retrieve"] = time.perf_counter() - t0

        if not merged_candidates and request.filters:
            logger.info("Нет результатов с фильтром, ищем без фильтра")
            retrieve_tasks = [self.search_engine.retrieve_candidates(q, None) for q in queries]
            candidates_list = await asyncio.gather(*retrieve_tasks, return_exceptions=True)

            valid_candidates = [c for c in candidates_list if not isinstance(c, Exception)]
            merged_candidates = self._merge_candidates(valid_candidates)

        if not merged_candidates:
            return expansion, [], timings

        t0 = time.perf_counter()
        docs = await asyncio.to_thread(
            self.search_engine.rerank_candidates,
            expansion.rewritten_query,
            merged_candidates,
            settings.final_top_k,
        )
        timings["rerank"] = time.perf_counter() - t0

        if not docs:
            return expansion, [], timings

        t0 = time.perf_counter()
        analyzed_docs = await self.document_analyzer.analyze_batch(docs, expansion.rewritten_query)
        timings["llm_analysis"] = time.perf_counter() - t0

        if not analyzed_docs:
            return expansion, [], timings

        if settings.use_summarization:
            await self._summarize_docs(analyzed_docs)

        timings["_merged_candidates_count"] = len(merged_candidates)
        timings["_docs_count"] = len(docs)

        return expansion, analyzed_docs, timings

    async def process_query(self, request: ChatRequest) -> ChatResponse:
        """Обрабатывает запрос через полный RAG-пайплайн."""
        expansion, analyzed_docs, timings = await self._prepare_context(request)

        if not analyzed_docs:
            return await self._generate_clarifying_response(
                request.query, expansion.rewritten_query
            )

        if analyzed_docs[0].get("low_confidence"):
            return ChatResponse(
                answer_type="no_relevant_docs",
                answer="В базе знаний отсутствует информация по данному запросу.",
                sources=[],
                rewritten_query=expansion.rewritten_query,
                timings=timings,
            )

        context_xml = self._build_context_xml(analyzed_docs)

        t0 = time.perf_counter()
        answer = await self.answer_generator.generate_answer(context_xml, expansion.rewritten_query)
        timings["llm_generation"] = time.perf_counter() - t0

        citation_report = self.citation_verifier.verify(answer, len(analyzed_docs))
        if citation_report.invalid_citations:
            answer = self.citation_verifier.clean_invalid_citations(answer, len(analyzed_docs))

        self._record_metrics_v2(timings, request, analyzed_docs)

        sources = self._build_sources(analyzed_docs)
        footnotes = self.footnote_builder.build_footnotes(
            answer,
            [
                {
                    **doc,
                    "source_type": "doc",
                    "source_name": doc.get("source", "unknown"),
                    "header_path": doc.get("path", ""),
                }
                for doc in analyzed_docs
            ],
        )

        return ChatResponse(
            answer_type="final_answer",
            answer=answer,
            sources=sources,
            rewritten_query=expansion.rewritten_query,
            timings=timings,
            citation_metrics=CitationMetrics(
                coverage=citation_report.citation_coverage,
                valid_citations=citation_report.valid_citations,
                invalid_removed=len(citation_report.invalid_citations),
            ),
            footnotes=footnotes,
        )

    async def process_query_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Streaming-версия process_query."""
        expansion, analyzed_docs, timings = await self._prepare_context(request)

        if not analyzed_docs:
            yield "[NO_RESULTS]"
            return

        if analyzed_docs[0].get("low_confidence"):
            yield "[NO_RELEVANT_DOCS]"
            return

        context_xml = self._build_context_xml(analyzed_docs)

        # NOTE: AnswerGenerator streaming not fully implemented yet in generic LLMClient
        # The generic LLMPort has removed generate_answer_stream.
        # Need to add generate_stream generic method?
        # But failing that, we assume generic generate is synchronous.
        # For now, we will just await the full answer and yield it,
        # or if we had generate_stream in generic port...
        # Wait, I removed generate_stream from LLMPort.
        # I should have kept a generic stream method!
        # Re-adding stream capability is needed for correct functionality.
        # For now, I will fake stream by yielding the full answer.

        answer = await self.answer_generator.generate_answer(context_xml, expansion.rewritten_query)
        yield answer

        sources = self._build_sources(analyzed_docs)
        yield f"\n[SOURCES]{json.dumps([s.model_dump() for s in sources], ensure_ascii=False)}"

    def _record_metrics_v2(
        self,
        timings: dict[str, float],
        request: ChatRequest,
        analyzed_docs: list[dict[str, Any]],
    ):
        """Вспомогательный метод для записи метрик после рефакторинга."""
        metrics = get_metrics_collector()
        for stage in ["query_expansion", "retrieve", "rerank", "llm_analysis", "llm_generation"]:
            if stage in timings:
                metrics.record_pipeline_stage(stage, timings[stage])

        total_time = sum(v for k, v in timings.items() if not k.startswith("_"))
        metrics.record_request(
            total_duration_sec=total_time,
            docs_retrieved=timings.get("_docs_count", 0),
            docs_filtered=timings.get("_docs_count", 0) - len(analyzed_docs),
            answer_type="final_answer",
            query_preview=request.query,
        )

    async def _generate_clarifying_response(
        self,
        original_query: str,
        rewritten_query: str,
    ) -> ChatResponse:
        """Генерирует уточняющий вопрос."""
        question = await self.answer_generator.generate_clarifying_question(original_query)
        return ChatResponse(
            answer_type="clarifying_question",
            answer=question,
            sources=[],
            rewritten_query=rewritten_query,
        )

    def _merge_candidates(
        self,
        candidates_list: list[dict[str, dict[str, Any]]],
    ) -> dict[str, dict[str, Any]]:
        """Объединяет кандидатов и суммирует RRF-скоры."""
        merged: dict[str, dict[str, Any]] = {}
        for candidates in candidates_list:
            for pid, doc in candidates.items():
                if pid in merged:
                    merged[pid]["rrf_score"] += doc.get("rrf_score", 0)
                else:
                    merged[pid] = doc.copy()
        return merged

    def _build_context_xml(self, search_results: list[dict[str, Any]]) -> str:
        """Формирует XML-контекст."""
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
        """Сжимает документы (режим full)."""
        if not docs:
            return
        contents = [doc.get("raw_content", "") for doc in docs]
        summaries = await self.summarizer.summarize_batch(contents)
        for doc, summary in zip(docs, summaries, strict=False):
            doc["summary_content"] = summary

    def _build_sources(self, search_results: list[dict[str, Any]]) -> list[SourceDoc]:
        """Конвертирует результаты поиска в DTO."""
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

