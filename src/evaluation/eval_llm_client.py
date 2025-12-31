"""LLM-клиент для evaluation через OpenRouter.

Совместим с интерфейсом LLMClient — можно передать в RAGService.
"""

import logging
import time

from openai import AsyncOpenAI

from src.application.prompts import (
    SYSTEM_ANALYZER,
    SYSTEM_CLARIFY,
    SYSTEM_MAIN,
    SYSTEM_QUERY_EXPANSION,
    format_analysis_prompt,
    format_query_rewrite_prompt,
)
from src.config.settings import settings
from src.config.telemetry import traced_operation
from src.domain.models import DocAnalysis, QueryExpansion

logger = logging.getLogger(__name__)


class EvalLLMClient:
    """LLM-клиент для evaluation через OpenRouter API.

    Совместим с LLMClient по интерфейсу для использования в RAGService.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        """Инициализирует клиент.

        Args:
            api_key: OpenRouter API ключ.
            base_url: OpenRouter base URL.
            model: Модель для RAG (eval_rag_model).

        """
        self.api_key = api_key or settings.openrouter_api_key
        self.base_url = base_url or settings.openrouter_base_url
        self.model = model or settings.eval_rag_model

        if not self.api_key:
            raise ValueError("OpenRouter API ключ не задан (OPENROUTER_API_KEY)")

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=120.0,
        )

        logger.info("EvalLLMClient инициализирован: model=%s", self.model)

    def _get_routing_config(self) -> dict:
        """Возвращает настройки маршрутизации для OpenRouter."""
        return {
            "provider": {
                "sort": "throughput",
                "allow_fallbacks": True
            }
        }

    async def expand_query(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> QueryExpansion:
        """Расширяет запрос.

        Args:
            query: Запрос пользователя.
            history: История диалога.

        Returns:
            QueryExpansion с основным запросом и вариациями.

        """
        recent = history[-4:] if history else []
        history_text = (
            "\n".join(
                [
                    f"{'User' if msg['role'] == 'user' else 'Bot'}: {msg['content'][:200]}..."
                    for msg in recent
                ]
            )
            if recent
            else "Нет истории."
        )

        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.expand_query", {"model": self.model}):
                response = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_QUERY_EXPANSION},
                        {
                            "role": "user",
                            "content": format_query_rewrite_prompt(history_text, query),
                        },
                    ],
                    response_format=QueryExpansion,
                    temperature=0.0,
                    max_tokens=300,
                    extra_body=self._get_routing_config(),
                )
                result = response.choices[0].message.parsed
                duration = time.perf_counter() - t0
                logger.debug(
                    "Query expansion (%.2fs): %s", duration, result.rewritten_query[:50]
                )
                return result
        except Exception as e:
            logger.warning("Ошибка расширения запроса: %s", e)

            return QueryExpansion(rewritten_query=query, variations=[query, query])

    async def analyze_document(
        self,
        content: str,
        query: str,
    ) -> DocAnalysis | None:
        """Анализирует документ на релевантность через LLM.

        Args:
            content: Текст документа.
            query: Запрос пользователя для оценки релевантности.

        Returns:
            DocAnalysis с оценкой релевантности или None при ошибке.

        """
        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.analyze_doc", {"model": self.model}):
                response = await self.client.beta.chat.completions.parse(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_ANALYZER},
                        {"role": "user", "content": format_analysis_prompt(query, content)},
                    ],
                    response_format=DocAnalysis,
                    temperature=0.0,
                    max_tokens=2000,
                    extra_body=self._get_routing_config(),
                )
                result = response.choices[0].message.parsed
                duration = time.perf_counter() - t0
                logger.debug(
                    "Doc analysis (%.2fs): score=%d", duration, result.relevance_score
                )
                return result
        except Exception as e:
            logger.warning("Ошибка анализа документа: %s", e)
            return None

    async def generate_clarifying_question(self, original_query: str) -> str:
        """Генерирует уточняющий вопрос.

        Args:
            original_query: Исходный запрос.

        Returns:
            Уточняющий вопрос.

        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_CLARIFY},
                    {"role": "user", "content": original_query},
                ],
                temperature=0.3,
                max_tokens=200,
                extra_body=self._get_routing_config(),
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            logger.warning("Ошибка генерации уточняющего вопроса: %s", e)
            return "Не могли бы вы уточнить ваш запрос?"

    async def generate_answer(
        self,
        context_xml: str,
        query: str,
    ) -> str:
        """Генерирует финальный ответ на основе контекста.

        Args:
            context_xml: XML-контекст с документами.
            query: Запрос пользователя.

        Returns:
            Сгенерированный ответ.

        Raises:
            RuntimeError: При ошибке генерации.

        """
        t0 = time.perf_counter()
        try:
            with traced_operation("eval_llm.generate", {"model": self.model}):
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": SYSTEM_MAIN},
                        {
                            "role": "user",
                            "content": f"CONTEXT:\n{context_xml}\n\nQUESTION: {query}",
                        },
                    ],
                    stream=False,
                    temperature=0.0,
                    extra_body=self._get_routing_config(),
                )
                answer = response.choices[0].message.content or ""
                duration = time.perf_counter() - t0
                logger.debug("Answer generation (%.2fs): %d chars", duration, len(answer))
                return answer
        except Exception as e:
            logger.error("Ошибка генерации LLM: %s", e)
            raise RuntimeError(f"Ошибка генерации ответа: {e}") from e
