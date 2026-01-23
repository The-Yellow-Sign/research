import logging
from abc import ABC, abstractmethod
from typing import Any

from src.application.dto import ChatRequest, ChatResponse
from src.application.services.rag_service import RAGService
from src.application.use_cases.agent_controller import AgentController, AgentResponse
from src.evaluation.schemas import Footnote, RAGOutput, RetrievedContext, TraceStep

logger = logging.getLogger(__name__)


class BaseSystemAdapter(ABC):
    """Абстрактный адаптер для целей оценки."""

    @abstractmethod
    async def run(self, query: str) -> RAGOutput:
        """Запускает адаптер для выполнения запроса."""
        pass


def map_chat_response_to_rag_output(response: ChatResponse) -> RAGOutput:
    """Преобразует ChatResponse (RAG) в RAGOutput."""
    contexts = []
    if response.sources:
        for doc in response.sources:
            contexts.append(
                RetrievedContext(source=doc.source_file, content=doc.content, score=doc.score)
            )

    footnotes = []
    if response.footnotes:
        for fn in response.footnotes:
            footnotes.append(
                Footnote(
                    doc_id=fn.id,
                    service=fn.service or "unknown",
                    title=fn.title,
                    source_file=fn.source,
                    quote=fn.quote,
                    source_type=fn.source_type,
                    header_path=fn.header_path,
                    url=fn.url,
                )
            )

    timings = {}
    latency_sec = 0.0

    if response.timings:
        t = response.timings

        timings["query_expansion_sec"] = t.get("query_expansion", 0.0)
        timings["retrieve_sec"] = t.get("retrieve", 0.0)
        timings["rerank_sec"] = t.get("rerank", 0.0)
        timings["llm_analysis_sec"] = t.get("llm_analysis", 0.0)
        timings["llm_generation_sec"] = t.get("llm_generation", 0.0)

        latency_sec = sum(timings.values())
        timings["total_sec"] = latency_sec

    return RAGOutput(
        generated_answer=response.answer,
        retrieved_contexts=contexts,
        footnotes=footnotes,
        latency_sec=latency_sec,
        timings=timings,
        answer_type=response.answer_type,
        trace=[],
    )


class AgentAdapter(BaseSystemAdapter):
    """Адаптер для AgentController."""

    def __init__(self, controller: AgentController):
        """Инициализирует адаптер с контроллером агента."""
        self.controller = controller

    def _process_trace_events(self, events: list[dict[str, Any]]) -> list[TraceStep]:
        """Преобразует сырые события трассировки в объекты TraceStep."""
        trace_steps = []
        current_step = None
        step_idx = 1

        for event in events:
            if event["type"] == "thinking":
                if current_step:
                    trace_steps.append(current_step)
                current_step = TraceStep(
                    step=step_idx,
                    thought=event["name"] + ": " + str(event.get("result", "")),
                    action="",
                    params={},
                    observation="",
                )
                step_idx += 1
            elif event["type"] == "tool_call":
                if current_step is None:
                    current_step = TraceStep(
                        step=step_idx,
                        thought="Implicit thought (tool call)",
                        action=event["name"],
                        params=event.get("args") or {},
                        observation=str(event.get("result", "")),
                    )
                    step_idx += 1
                else:
                    current_step.action = event["name"]
                    current_step.params = event.get("args") or {}
                    current_step.observation = str(event.get("result", ""))
                    trace_steps.append(current_step)
                    current_step = None

        if current_step:
            trace_steps.append(current_step)

        return trace_steps

    def _calculate_timings(
        self, trace_events: list[dict[str, Any]], total_sec: float
    ) -> dict[str, float]:
        """Вычисляет детализированные тайминги из событий трассировки."""
        timings = {
            "retrieve_sec": 0.0,
            "rerank_sec": 0.0,
            "llm_generation_sec": 0.0,
            "query_expansion_sec": 0.0,
            "total_sec": total_sec,
        }

        for event in trace_events:
            e_type = event.get("type")
            e_name = event.get("name")
            duration = event.get("duration_ms", 0.0) / 1000.0
            metadata = event.get("metadata", {})

            if e_type == "thinking":
                timings["llm_generation_sec"] += duration

            elif e_type == "tool_call":
                if e_name == "rag_search":
                    tool_timings = metadata.get("timings", {})
                    t_retrieve = tool_timings.get("retrieve_sec") or tool_timings.get(
                        "retrieve", 0.0
                    )
                    timings["retrieve_sec"] += t_retrieve

                    t_rerank = tool_timings.get("rerank_sec") or tool_timings.get("rerank", 0.0)
                    timings["rerank_sec"] += t_rerank

                    if (
                        not tool_timings
                        and not metadata.get("retrieve_sec")
                        and not metadata.get("retrieve")
                    ):
                        timings["retrieve_sec"] += duration

                elif e_name == "query_expansion":
                    timings["query_expansion_sec"] += duration

        return timings

    async def run(self, query: str) -> RAGOutput:
        """Запускает агента на запрос и возвращает RAGOutput."""
        response: AgentResponse = await self.controller.run(query)

        contexts = []
        if response.retrieved_docs:
            all_docs = [
                RetrievedContext(
                    source=doc.source_file,
                    content=doc.content,
                    score=doc.score,
                )
                for doc in response.retrieved_docs
            ]

            if response.citation_metrics and response.citation_metrics.valid_citations:
                valid_ids = set(response.citation_metrics.valid_citations)
                contexts = []
                for i, doc in enumerate(all_docs):
                    if (i + 1) in valid_ids:
                        contexts.append(doc)

                logger.info(
                    "Filtered RAG context: kept %d/%d documents based on citations",
                    len(contexts),
                    len(all_docs),
                )
            else:
                logger.warning(
                    "Agent used no valid citations (or metrics missing). "
                    "Fallback to using ALL %d collected docs for evaluation.",
                    len(all_docs),
                )
                contexts = all_docs

        trace_steps = []
        if response.trace and "events" in response.trace:
            trace_steps = self._process_trace_events(response.trace["events"])

        footnotes = []
        if response.footnotes:
            for fn in response.footnotes:
                footnotes.append(
                    Footnote(
                        doc_id=fn.id,
                        service=fn.service or "unknown",
                        title=fn.title,
                        source_file=fn.source,
                        quote=fn.quote,
                        source_type=fn.source_type,
                        header_path=fn.header_path,
                        url=fn.url,
                    )
                )

        if response.trace and "events" in response.trace:
            timings = self._calculate_timings(response.trace["events"], response.total_time_sec)
        else:
            timings = {
                "retrieve_sec": 0.0,
                "rerank_sec": 0.0,
                "llm_generation_sec": 0.0,
                "query_expansion_sec": 0.0,
                "total_sec": response.total_time_sec,
            }

        return RAGOutput(
            generated_answer=response.answer,
            retrieved_contexts=contexts,
            footnotes=footnotes,
            latency_sec=response.total_time_sec,
            trace=trace_steps,
            timings=timings,
        )


class RAGAdapter(BaseSystemAdapter):
    """Адаптер для стандартного RAGService."""

    def __init__(self, service: RAGService):
        """Инициализирует адаптер с сервисом RAG."""
        self.service = service

    async def run(self, query: str) -> RAGOutput:
        """Запускает сервис RAG на запрос и возвращает RAGOutput."""
        request = ChatRequest(query=query)
        response = await self.service.process_query(request)
        return map_chat_response_to_rag_output(response)
