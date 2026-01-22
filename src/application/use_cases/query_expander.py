"""Use Case: Расширение запросов (Query Expansion).

Отвечает за:
- Переписывание запроса с учётом истории диалога
- Генерацию вариаций запроса для улучшения полноты поиска
"""

import hashlib
import logging
from collections import OrderedDict

from src.application.prompts.registry import PromptRegistry
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
        self._prompt_registry = PromptRegistry()

        # Simple in-memory cache
        self._expand_cache: OrderedDict[str, QueryExpansion] = OrderedDict()
        self._cache_max_size = 100

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

        # 1. Check Cache
        recent = history[-4:] if history else []
        history_content = "".join(f"{m['role']}:{m['content'][:100]}" for m in recent)
        cache_key = hashlib.sha256(f"{query}:{history_content}".encode()).hexdigest()[:16]

        if cache_key in self._expand_cache:
            logger.debug("Query Expansion cache hit: %s", query[:50])
            self._expand_cache.move_to_end(cache_key)
            return self._expand_cache[cache_key]

        # 2. Prepare Prompt
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

        messages = [
            {
                "role": "system",
                "content": self._prompt_registry.get("system_query_expansion"),
            },
            {
                "role": "user",
                "content": self._prompt_registry.format(
                    "user_rewrite", history=history_text, query=query
                ),
            },
        ]

        # 3. Call LLM
        try:
            result = await self.llm.generate_structured(
                messages=messages,
                response_model=QueryExpansion,
                max_tokens=300,
                temperature=0.0,
            )

            # Post-process
            if result and result.variations:
                result.variations = [v[:100] for v in result.variations]

            # Cache
            self._expand_cache[cache_key] = result
            if len(self._expand_cache) > self._cache_max_size:
                self._expand_cache.popitem(last=False)

            logger.info(
                "Query Expansion: основной='%s', вариации=%s",
                result.rewritten_query,
                result.variations,
            )
            return result

        except Exception as e:
            logger.warning("Ошибка расширения запроса: %s", e)
            # Fallback
            return QueryExpansion(
                rewritten_query=query,
                variations=[query, f"{query} details"],
            )

    def get_all_queries(self, expansion: QueryExpansion) -> list[str]:
        """Возвращает все запросы для поиска.

        Args:
            expansion: Результат расширения запроса.

        Returns:
            Список запросов: основной + вариации.

        """
        return [expansion.rewritten_query] + expansion.variations
