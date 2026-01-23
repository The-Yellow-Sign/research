"""AgentController — главный оркестратор ReAct-цикла.

Реализует паттерн ReAct (Reason + Act) для агентного RAG.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any, AsyncIterator

import tiktoken
from openai import APIConnectionError, APITimeoutError, RateLimitError
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.application.dto.responses import CitationMetrics
from src.application.prompts.registry import PromptRegistry
from src.application.services.citation_formatter import CitationFootnoteBuilder
from src.application.services.citation_verifier import CitationVerifier
from src.application.tools import BaseTool
from src.application.use_cases.agent_models import (
    AgentAction,
    AgentDecision,
    AgentEvent,
    AgentEventType,
    AgentReflection,
    AgentResponse,
    AgentThought,
)
from src.application.use_cases.agent_tracer import AgentTracer
from src.application.use_cases.observation_manager import ObservationManager
from src.application.use_cases.query_decomposer import QueryDecomposer
from src.application.use_cases.tool_cache import ToolCallCache
from src.config import settings
from src.domain.models.response import SourceDoc
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class AgentController:
    """ReAct Agent для DevOps RAG.

    Координирует цикл think → act → observe → decide.
    """

    CITATION_PATTERN = re.compile(r"\[(\d+)\]")

    def __init__(
        self,
        llm: LLMPort,
        tools: list[BaseTool],
        model: str | None = None,
    ) -> None:
        self.llm = llm
        self.tools = {t.name: t for t in tools}
        self.model = model or settings.models.main

        self.model = model or settings.models.main

        # self.client removed - strict usage of LLMPort


        self.decomposer = QueryDecomposer(self.llm)
        self.tokenizer = (
            tiktoken.get_encoding("cl100k_base") if "tiktoken" in globals() else None
        )

        self.tracer = AgentTracer()
        self.citation_verifier = CitationVerifier()
        self.footnote_builder = CitationFootnoteBuilder()
        self.prompt_registry = PromptRegistry()
        self.tool_cache = ToolCallCache(ttl_sec=settings.tool_cache_ttl)

    async def _prefetch_expanded_queries(
        self,
        decomposed_queries: list[str],
        observations: ObservationManager,
        collected_docs: list[Any],
    ) -> None:
        """Предварительный поиск RAG для расширенных запросов с параллельным выполнением."""
        if not decomposed_queries:
            return

        if len(decomposed_queries) > 1:
            parallel_obs = await self._execute_parallel_searches(decomposed_queries, collected_docs)
            for obs in parallel_obs:
                observations.add(obs, priority=2)
            return

        # Один запрос — обычный поиск
        if "rag_search" not in self.tools:
            return

        eq = decomposed_queries[0]
        tool = self.tools["rag_search"]
        with self.tracer.trace_tool_call("rag_search", {"query": eq}) as ctx:
            result = await tool.execute(query=eq)
            ctx.set_result(result.data if result.success else f"Error: {result.error}")
            if result.metadata:
                ctx.update_metadata(**result.metadata)

        if result.success:
            data = result.data
            if result.metadata and "documents" in result.metadata:
                new_docs = result.metadata["documents"]
                current_offset = len(collected_docs)
                collected_docs.extend(new_docs)
                data = self._reindex_citations(data, current_offset)

            observations.add(
                f"[rag_search: {eq}] {data[: settings.agent_observation_max_chars]}",
                priority=2,
            )

    def _reindex_citations(self, text: str, offset: int) -> str:
        """Переиндексирует [N] ссылки с заданным смещением.

        Args:
            text: Текст с цитатами вида [1], [2].
            offset: Смещение для индексов.

        Returns:
            Текст с обновленными индексами.

        """

        def replacer(match: re.Match) -> str:
            return f"[{int(match.group(1)) + offset}]"

        return self.CITATION_PATTERN.sub(replacer, text)

    def _build_response(
        self,
        answer: str,
        sources: list[str],
        step: int,
        start_time: float,
        collected_docs: list[Any] | None = None,
    ) -> AgentResponse:
        """Собирает финальный ответ AgentResponse с трассировкой."""
        trace = self.tracer.end_trace()

        footnotes = []
        citation_metrics = None
        source_docs = []

        if collected_docs:
            citation_report = self.citation_verifier.verify(answer, len(collected_docs))
            if citation_report.invalid_citations:
                logger.warning(
                    "Invalid citations detected: %s (valid: 1-%d)",
                    citation_report.invalid_citations,
                    len(collected_docs),
                )
                answer = self.citation_verifier.clean_invalid_citations(answer, len(collected_docs))

            for i, d in enumerate(collected_docs, 1):
                source_type = d.get("source_type", "doc")
                if source_type == "doc":
                    source_docs.append(
                        SourceDoc(
                            doc_id=i,
                            rank=i,
                            score=d.get("score", 0),
                            service=d.get("service", "unknown"),
                            source_file=d.get("source_name") or d.get("source", "unknown"),
                            header_path=d.get("header_path", ""),
                            content=str(d.get("raw_content") or d.get("content", "")),
                        )
                    )

            footnotes = self.footnote_builder.build_footnotes(answer, collected_docs)

            citation_metrics = CitationMetrics(
                coverage=citation_report.citation_coverage,
                valid_citations=citation_report.valid_citations,
                invalid_removed=len(citation_report.invalid_citations),
            )

        return AgentResponse(
            answer=answer,
            sources=sources,
            steps=step,
            total_time_sec=time.perf_counter() - start_time,
            trace=trace.to_dict() if trace else None,
            footnotes=footnotes,
            citation_metrics=citation_metrics,
            retrieved_docs=source_docs,
        )

    async def _execute_tool(
        self, action: str, params: dict[str, Any], collected_docs: list[Any]
    ) -> str:
        """Выполняет инструмент и возвращает строку наблюдения.

        Обрабатывает глобальную индексацию документов для rag_search.
        """
        tool = self.tools[action]
        with self.tracer.trace_tool_call(action, params) as ctx:
            result = await asyncio.wait_for(
                tool.execute(**params),
                timeout=settings.agent_timeout / settings.agent_max_iterations,
            )
            ctx.set_result(result.data if result.success else f"Error: {result.error}")

            if result.metadata:
                logger.info("Tool %s metadata: %s", action, result.metadata)
                ctx.update_metadata(**result.metadata)
            elif result.success:
                logger.warning("Tool %s returned no metadata", action)

        if result.success:
            data = result.data

            if (
                action == AgentAction.RAG_SEARCH.value
                and result.metadata
                and "documents" in result.metadata
            ):
                new_docs = result.metadata["documents"]
                current_offset = len(collected_docs)
                collected_docs.extend(new_docs)
                data = self._reindex_citations(data, current_offset)
                logger.info("Rewrote doc indices with offset %d", current_offset)

            elif (
                action == AgentAction.WEB_SEARCH.value
                and result.metadata
                and "web_sources" in result.metadata
            ):
                new_sources = result.metadata["web_sources"]
                current_offset = len(collected_docs)
                collected_docs.extend(new_sources)
                data = self._reindex_citations(data, current_offset)
                logger.info("Rewrote web indices with offset %d", current_offset)

            return f"[{action}] {data[: settings.agent_result_max_chars]}"

        return f"[{action}] Ошибка: {result.error}"

    async def run(self, query: str, history: list[dict[str, str]] | None = None) -> AgentResponse:
        """Выполняет ReAct loop синхронно, используя run_stream.

        Args:
            query: Запрос пользователя.
            history: История диалога (опционально).

        Returns:
            AgentResponse с финальным ответом.

        """
        final_response = None

        async for event in self.run_stream(query, history):
            if event.type == AgentEventType.ANSWER:
                if event.agent_response:
                    final_response = event.agent_response
                else:
                    final_response = AgentResponse(
                        answer=event.content,
                        sources=event.sources,
                        steps=0,
                        total_time_sec=0.0,
                    )

        if final_response:
            return final_response

        return AgentResponse(
            answer="Internal Error: No response generated.", sources=[], steps=0, total_time_sec=0.0
        )

    async def run_stream(  # noqa: C901
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[AgentEvent]:
        """Выполняет ReAct loop с streaming событий.

        Args:
            query: Запрос пользователя.
            history: История диалога.

        Yields:
            AgentEvent с промежуточными результатами.

        """
        trace_id = str(uuid.uuid4())[:8]
        self.tracer.start_trace(trace_id, query)
        start_time = time.perf_counter()

        observations = ObservationManager(max_tokens=settings.agent_observation_max_tokens)
        collected_docs: list[Any] = []
        tool_call_counts: dict[str, int] = {}
        system_error_count = 0
        MAX_SYSTEM_ERRORS = settings.agent_max_system_errors
        max_iterations = settings.agent_max_iterations

        stream_msgs = self.prompt_registry.get("stream_messages")
        yield AgentEvent(
            type=AgentEventType.THINKING,
            content=stream_msgs.get("analyzing_query", "Анализирую запрос..."),
        )

        with self.tracer.trace_tool_call("query_expansion", {"query": query}) as ctx:
            decomposed = await self.decomposer.decompose(query, history=history)
            ctx.set_result(str(decomposed))

        if len(decomposed.expanded_queries) > 1:
            content = stream_msgs.get("decomposed_query", "").format(
                queries=", ".join(decomposed.expanded_queries)
            )
            yield AgentEvent(type=AgentEventType.THINKING, content=content)

        await self._prefetch_expanded_queries(
            decomposed.expanded_queries, observations, collected_docs
        )
        if collected_docs:
            content = stream_msgs.get("prefetch_found", "").format(count=len(collected_docs))
            yield AgentEvent(type=AgentEventType.THINKING, content=content)

        for _step in range(max_iterations):
            try:
                is_last_step = _step == max_iterations - 1
                thought = await self._think(
                    query, observations, step=_step + 1, force_final=is_last_step, history=history
                )

                yield AgentEvent(
                    type=AgentEventType.THINKING,
                    content=str(thought.thought),
                )
                logger.info("Step %d: action=%s", _step + 1, thought.action)

                if thought.action == AgentAction.FINAL_ANSWER:
                    candidate_answer = str(thought.params.get("answer", ""))

                    hallucination_valid = await self._validate_answer_hallucinations(
                        candidate_answer, collected_docs, observations, stream_msgs
                    )
                    if not hallucination_valid:
                        continue

                    sources = thought.params.get("sources", [])

                    # Phase 3: Self-Reflection (Conditional)
                    should_reflect = settings.agent_reflection_enabled and (
                        len(collected_docs) >= settings.agent_reflection_min_sources
                        or _step >= settings.agent_reflection_min_steps
                    )

                    if should_reflect:
                        approved, feedback = await self._reflect_on_answer(
                            query, candidate_answer, observations.as_list()
                        )
                    else:
                        approved, feedback = True, ""

                    if not approved and _step < max_iterations - 1:
                        observations.add(f"РЕФЛЕКСИЯ: {feedback}", priority=3)
                        yield AgentEvent(
                            type=AgentEventType.THINKING, content=f"Рефлексия: {feedback}"
                        )
                        continue

                    agent_response = self._build_response(
                        candidate_answer, sources, _step + 1, start_time, collected_docs
                    )

                    yield AgentEvent(
                        type=AgentEventType.ANSWER,
                        content=candidate_answer,
                        sources=sources,
                        agent_response=agent_response,
                    )
                    return

                if thought.action == AgentAction.CLARIFYING_QUESTION:
                    question = str(thought.params.get("question", "Уточните ваш запрос"))
                    agent_response = self._build_response(
                        f"❓ {question}", [], _step + 1, start_time, collected_docs
                    )
                    yield AgentEvent(
                        type=AgentEventType.ANSWER,
                        content=f"❓ {question}",
                        sources=[],
                        agent_response=agent_response,
                    )
                    return

                if not thought.action:
                    error_thoughts = self.prompt_registry.get("error_thoughts")
                    err_msg = error_thoughts.get("empty_action", "")
                    observations.add(err_msg, priority=3)
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        content=stream_msgs.get("retry_on_error", "").format(
                            error_type="empty_action"
                        ),
                    )
                    continue

                if thought.action in (AgentAction.TOKEN_LIMIT, AgentAction.INVALID_SCHEMA):
                    system_error_count += 1
                    if system_error_count >= MAX_SYSTEM_ERRORS:
                        logger.error(
                            "Too many system errors (%d), aborting loop", system_error_count
                        )
                        break

                    observations.add(
                        f"СИСТЕМА: Ошибка ({thought.action.value}). Пробую еще раз.", priority=3
                    )
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        content=stream_msgs.get("retry_on_error", "").format(
                            error_type=thought.action.value
                        ),
                    )
                    continue

                action_val = (
                    thought.action.value if hasattr(thought.action, "value") else thought.action
                )
                if action_val not in self.tools:
                    error_thoughts = self.prompt_registry.get("error_thoughts")
                    err_msg = error_thoughts.get("tool_not_found", "").format(
                        tool_name=action_val,
                        available_tools=list(self.tools.keys()),
                    )
                    observations.add(err_msg, priority=3)
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        content=f"Инструмент '{action_val}' не найден.",
                    )
                    continue

                tool_call_counts[action_val] = tool_call_counts.get(action_val, 0) + 1
                if tool_call_counts[action_val] > 5:
                    error_thoughts = self.prompt_registry.get("error_thoughts")
                    err_msg = error_thoughts.get("tool_limit_exceeded", "").format(
                        tool_name=action_val, count=5
                    )
                    observations.add(err_msg, priority=3)
                    yield AgentEvent(
                        type=AgentEventType.ERROR,
                        content=f"Слишком много вызовов {action_val}.",
                    )
                    continue

                yield AgentEvent(
                    type=AgentEventType.TOOL_CALL,
                    tool=action_val,
                    params=thought.params,
                )

                # Check cache first
                cached = self.tool_cache.get(action_val, thought.params)

                if cached is not None:
                    result, cached_docs = cached
                    collected_docs.extend(cached_docs)
                    logger.info("Using cached result for %s", action_val)
                else:
                    docs_before = len(collected_docs)
                    result = await self._execute_tool(action_val, thought.params, collected_docs)
                    new_docs = collected_docs[docs_before:]
                    if "Ошибка:" not in result:
                        self.tool_cache.set(action_val, thought.params, (result, new_docs))

                yield AgentEvent(type=AgentEventType.TOOL_RESULT, content=result, tool=action_val)

                if "Ошибка:" in result:
                    error_hints = self.prompt_registry.get("error_recovery") or {}
                    hint = error_hints.get("tool_error", "")
                    observations.add(f"{result}\n{hint}", priority=3)
                else:
                    observations.add(result, priority=2)

            except Exception as e:
                logger.error("Agent stream error: %s", e)
                observations.add(f"Ошибка: {e}", priority=3)
                yield AgentEvent(
                    type=AgentEventType.ERROR,
                    content=str(e),
                )

        fallback_msg = (
            "Не удалось найти ответ за отведённое количество шагов. "
            "Попробуйте переформулировать запрос."
        )

        fallback_response = AgentResponse(
            answer=fallback_msg,
            sources=[],
            steps=max_iterations,
            total_time_sec=time.perf_counter() - start_time,
            trace=self.tracer.end_trace().to_dict(),
        )

        yield AgentEvent(
            type=AgentEventType.ANSWER,
            content=fallback_msg,
            sources=[],
            agent_response=fallback_response,
        )

    async def _validate_answer_hallucinations(
        self,
        answer: str,
        collected_docs: list[Any],
        observations: ObservationManager,
        stream_msgs: dict[str, str],
    ) -> bool:
        """Проверяет ответ на галлюцинации через VerifyAnswerTool."""
        if not collected_docs:
            return True

        verifier_tool = self.tools.get("verify_answer")
        if not verifier_tool:
            return True

        context_text = "\n\n".join([str(d) for d in collected_docs])
        verification_result = await verifier_tool.execute(answer=answer, context=context_text)

        if verification_result.success:
            ver_data = verification_result.data
            try:
                parsed = json.loads(ver_data)
                is_valid = parsed.get("valid", True) if isinstance(parsed, dict) else True
            except json.JSONDecodeError:
                is_valid = "valid: false" not in ver_data.lower()

                if not is_valid:
                    logger.warning("Верификация не пройдена (Stream).")
                    fail_msg = (
                        "КРИТИЧЕСКОЕ СИСТЕМНОЕ НАБЛЮДЕНИЕ: Твой ответ не прошёл верификацию.\n"
                        f"Отчёт проверки: {ver_data}\n"
                        "Ты ОБЯЗАН исправить галлюцинации и попробовать снова."
                    )
                    observations.add(fail_msg, priority=3)
                    return False

        return True

    async def _reflect_on_answer(
        self,
        query: str,
        candidate_answer: str,
        observations: list[str],
    ) -> tuple[bool, str]:
        """Рефлексия: проверка качества ответа."""
        reflection_prompt_tpl = self.prompt_registry.get("reflection_prompt")
        if not reflection_prompt_tpl:
            return True, candidate_answer

        prompt = reflection_prompt_tpl.format(
            query=query,
            candidate_answer=candidate_answer,
            observations="\n".join(observations[-3:]),
        )

        try:
            reflection = await self.llm.generate_structured(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a senior DevOps engineer reviewing the assistant's "
                            "answer for accuracy and completeness."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=AgentReflection,
                max_tokens=settings.agent_max_tokens,
            )

            if reflection.is_approved:
                return True, candidate_answer

            return False, reflection.critique
        except Exception as e:
            logger.warning("Reflection failed: %s", e)
            return True, candidate_answer

    def _build_dynamic_hints(self, observations: ObservationManager) -> str:
        """Генерирует динамические подсказки на основе истории."""
        hints = []

        empty_count = observations.count_pattern("результатов: 0")
        if empty_count >= 2:
            hints.append(
                "⚠️ Предыдущие поиски в rag_search были пустыми. "
                "Попробуй web_search или переформулируй запрос."
            )

        error_count = observations.count_pattern("ОШИБКА:")
        if error_count >= 1:
            hints.append("⚠️ Были ошибки инструментов. Проверь параметры.")

        if not hints:
            return ""

        return "\n".join(hints)

    async def _execute_parallel_searches(
        self,
        queries: list[str],
        collected_docs: list[Any],
    ) -> list[str]:
        """Параллельное выполнение нескольких RAG-поисков."""
        rag_tool = self.tools.get(AgentAction.RAG_SEARCH.value)
        if not rag_tool:
            return []

        tasks = [rag_tool.execute(query=q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        new_observations = []
        for q, r in zip(queries, results, strict=True):
            if isinstance(r, Exception):
                new_observations.append(f"[search:{q}] Ошибка: {r}")
            else:
                new_observations.append(f"[search:{q}] {r.data[:500]}...")
                if hasattr(r, "docs") and r.docs:
                    collected_docs.extend(r.docs)

        return new_observations

    async def _think(  # noqa: C901
        self,
        query: str,
        observations: ObservationManager,
        step: int = 1,
        force_final: bool = False,
        history: list[dict[str, str]] | None = None,
    ) -> AgentThought:
        """Генерирует следующее действие через LLM используя Structured Output.

        Args:
            query: Исходный запрос.
            observations: Менеджер наблюдений.
            step: Текущий номер шага.
            force_final: Принудительно сгенерировать final_answer.
            history: История диалога.

        Returns:
            AgentThought с action и params.

        """
        obs_text = observations.get_context() if observations.observations else "Пока нет действий."

        # Add dynamic hints
        dynamic_hints = self._build_dynamic_hints(observations)
        if dynamic_hints:
            obs_text += f"\n\n## Динамические подсказки\n{dynamic_hints}"

        if force_final:
            hints = self.prompt_registry.get("urgency_hints")
            urgency_hint = hints.get("force_final", hints.get("late"))
        else:
            hints = self.prompt_registry.get("urgency_hints")
            urgency_hint = hints.get("late") if step >= 3 else hints.get("early")

        history_context = ""
        if history:
            history_lines = []
            for msg in history[-4:]:
                role = "Пользователь" if msg.get("role") == "user" else "Ассистент"
                content = msg.get("content", "")[:300]
                history_lines.append(f"{role}: {content}")
            history_context = "\n## Предыдущий контекст диалога\n" + "\n".join(history_lines)

        prompt = self.prompt_registry.format(
            "agent_think",
            query=query,
            observations=obs_text,
            step=step,
            max_steps=settings.agent_max_iterations,
            urgency_hint=urgency_hint,
        )

        if history_context:
            prompt = history_context + "\n\n" + prompt

        @retry(
            wait=wait_exponential(
                multiplier=settings.llm_retry_base_delay, max=settings.llm_retry_max_delay
            ),
            stop=stop_after_attempt(settings.llm_retry_attempts),
            retry=retry_if_exception_type(
                (APIConnectionError, RateLimitError, APITimeoutError)
            ),
            reraise=True,
        )
        async def _call_llm_with_retry():
            return await self.llm.generate_structured(
                messages=[
                    {
                        "role": "system",
                        "content": self.prompt_registry.format(
                            "agent_system",
                            few_shot_examples=self.prompt_registry.get("few_shot_examples")
                        )
                    },
                    {"role": "user", "content": prompt},
                ],
                response_model=AgentDecision,
                max_tokens=settings.agent_max_tokens,
                temperature=0.0
            )

        try:
            decision = await _call_llm_with_retry()
            # result is already the parsed model, no need to access choices[0].message.parsed

            if not decision:
                raise ValueError("Received empty decision from LLM")

            return AgentThought(
                thought=decision.thought, action=decision.tool_name, params=decision.params
            )

        except ValidationError as e:
            logger.warning("LLM produced invalid JSON schema: %s", e)
            return AgentThought(
                thought=self.prompt_registry.get("error_thoughts")
                .get("schema_validation", "")
                .format(error=str(e)),
                action=AgentAction.INVALID_SCHEMA,
                params={},
            )
        except Exception as e:
            if "LengthFinishReasonError" in str(type(e)):
                logger.warning("LLM hit token limit: %s", e)
                return AgentThought(
                    thought=self.prompt_registry.get("error_thoughts").get("token_limit", ""),
                    action=AgentAction.TOKEN_LIMIT,
                    params={},
                )
            raise e
