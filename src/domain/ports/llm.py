"""Port для LLM-клиента.

Определяет абстрактный интерфейс для взаимодействия с языковыми моделями.
Реализации (Adapters) находятся в infrastructure/llm/.
"""

from collections.abc import AsyncIterator
from typing import Protocol

from src.domain.models.query import DocAnalysis, QueryExpansion


class LLMPort(Protocol):
    """Абстракция для LLM-клиента.

    Определяет контракт для всех LLM-адаптеров (OpenAI, Anthropic, etc.).
    Позволяет подменять реализацию без изменения бизнес-логики.
    """

    async def expand_query(
        self,
        query: str,
        history: list[dict[str, str]],
    ) -> QueryExpansion:
        """Расширяет запрос с учётом истории диалога.

        Args:
            query: Исходный запрос пользователя.
            history: История диалога.

        Returns:
            QueryExpansion с основным запросом и вариациями.

        """
        ...

    async def analyze_document(
        self,
        content: str,
        query: str,
    ) -> DocAnalysis | None:
        """Анализирует документ на релевантность.

        Args:
            content: Текст документа.
            query: Запрос для оценки релевантности.

        Returns:
            DocAnalysis с оценкой и summary, или None при ошибке.

        """
        ...

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

        """
        ...

    async def generate_answer_stream(
        self,
        context_xml: str,
        query: str,
    ) -> AsyncIterator[str]:
        """Генерирует ответ в режиме streaming.

        Args:
            context_xml: XML-контекст с документами.
            query: Запрос пользователя.

        Yields:
            Токены ответа по мере генерации.

        """
        ...

    async def generate_clarifying_question(
        self,
        original_query: str,
    ) -> str:
        """Генерирует уточняющий вопрос при отсутствии релевантных документов.

        Args:
            original_query: Исходный запрос пользователя.

        Returns:
            Уточняющий вопрос.

        """
        ...

    async def check_health(self) -> bool:
        """Проверяет доступность LLM API.

        Returns:
            True если API доступно.

        """
        ...
