"""Use Case: Генерация ответов (Answer Generation).

Отвечает за:
- Генерацию финального ответа на основе контекста
- Streaming-генерацию
- Генерацию уточняющих вопросов
"""

import logging
import time

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.application.prompts.registry import PromptRegistry
from src.config import settings
from src.config.metrics import get_metrics_collector
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class AnswerGenerator:
    """Генератор ответов для RAG-пайплайна.

    Инкапсулирует логику промптинга для генерации ответов.
    """

    def __init__(self, llm: LLMPort) -> None:
        self.llm = llm
        self._prompt_registry = PromptRegistry()

    async def generate_answer(
        self,
        context_xml: str,
        query: str,
    ) -> str:
        """Генерирует финальный ответ на основе контекста."""
        if len(context_xml) > settings.max_context_chars:
            logger.warning(
                "Context truncated: %d -> %d chars", len(context_xml), settings.max_context_chars
            )
            context_xml = context_xml[: settings.max_context_chars] + "\n</documents>"

        t0 = time.perf_counter()
        metrics = get_metrics_collector()

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            reraise=True,
        )
        async def _call_with_retry():
            return await self.llm.generate(
                prompt=self._build_prompt(context_xml, query),
                max_tokens=settings.agent_max_tokens,
                # settings.agent_max_tokens is 10000, looks fine. Or hardcode 2000?
                # LLMClient code had no explicit max_tokens param in generate calls
                # usually, passed default 500 or specific.
                # Generic LLM generate defaults to 500. We need more for answer.
            )

        try:
            # We can't easily use "system" role in generic generate(prompt)
            # if it takes string.
            # But wait, generic LLMClient.generate takes just a prompt string
            # and sends it as user message?
            # Yes: messages=[{"role": "user", "content": prompt}]
            # If we need system prompt, we must use generate_structured or we need
            # a new method generate_chat(messages).
            # The approved implementation plan said:
            # `generate(messages, ...)` in LLMPort?
            # Let's check LLMPort again.
            # It says: async def generate(self, prompt: str, max_tokens: int = 500) -> str:
            # It takes a string prompt.
            # This is a limitation if we want System prompt separation.
            # Ideally we should update LLMPort to take messages list for
            # non-structured generation too.
            # Or we concat system prompt + user prompt.

            # Let's concat for now to stick to the interface I pushed.

            system_prompt = self._prompt_registry.get("system_main")
            user_content = f"CONTEXT:\n{context_xml}\n\nQUESTION: {query}"
            full_prompt = f"{system_prompt}\n\n{user_content}"

            # Use a large token limit for answers
            result = await self.llm.generate(full_prompt, max_tokens=4000)

            duration = time.perf_counter() - t0
            metrics.record_llm_call(
                "generate_answer",
                duration,
                len(full_prompt) // 4,
                len(result) // 4,
                "main",
            )  # Model naming?
            return result or ""

        except Exception as e:
            metrics.record_llm_call(
                "generate_answer",
                time.perf_counter() - t0,
                0,
                0,
                "main",
                False,
                str(e),
            )
            logger.error("Ошибка генерации LLM: %s", e)
            raise RuntimeError(f"Ошибка генерации ответа: {e}") from e

    async def generate_clarifying_question(self, original_query: str) -> str:
        """Генерирует уточняющий вопрос."""
        t0 = time.perf_counter()
        metrics = get_metrics_collector()
        try:
            system = self._prompt_registry.get("system_clarify")
            prompt = f"{system}\n\nUser Query: {original_query}"

            result = await self.llm.generate(prompt, max_tokens=200)

            duration = time.perf_counter() - t0
            metrics.record_llm_call(
                "clarifying_question",
                duration,
                len(prompt) // 4,
                len(result) // 4,
                "main",
            )
            return result or ""
        except Exception as e:
            logger.warning("Ошибка генерации уточняющего вопроса: %s", e)
            return "Не могли бы вы уточнить ваш запрос?"

    def _build_prompt(self, context: str, query: str) -> str:
        system = self._prompt_registry.get("system_main")
        return f"{system}\n\nCONTEXT:\n{context}\n\nQUESTION: {query}"
