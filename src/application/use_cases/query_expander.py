"""Use Case: Расширение запросов (Query Expansion).

Отвечает за:
- Переписывание запроса с учётом истории диалога
- Генерацию вариаций запроса для улучшения полноты поиска
"""

import logging

from src.domain.models.query import QueryExpansion
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class QueryExpander:
    """Расширитель запросов для RAG-пайплайна.

    Использует LLM для:
    - Контекстуализации запроса с учётом истории чата
    - Генерации альтернативных формулировок (синонимы, термины)

    """

    def __init__(self, llm: LLMPort) -> None:
        """Инициализация расширителя запросов.

        Args:
            llm: LLM-клиент, реализующий LLMPort.

        """
        self.llm = llm

    async def expand(
        self,
        query: str,
        history: list[dict[str, str]] | None = None,
    ) -> QueryExpansion:
        """Расширяет запрос с помощью LLM.

        Args:
            query: Исходный запрос пользователя.
            history: История диалога (опционально).

        Returns:
            QueryExpansion с основным запросом и вариациями.

        """
        history = history or []

        expansion = await self.llm.expand_query(query, history)

        logger.info(
            "Query Expansion: основной='%s', вариации=%s",
            expansion.rewritten_query,
            expansion.variations,
        )

        return expansion

    def get_all_queries(self, expansion: QueryExpansion) -> list[str]:
        """Возвращает все запросы для поиска.

        Args:
            expansion: Результат расширения запроса.

        Returns:
            Список запросов: основной + вариации.

        """
        return [expansion.rewritten_query] + expansion.variations
