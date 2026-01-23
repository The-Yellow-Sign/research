"""Query Decomposer + Expander — разбивает и расширяет запросы.

Использует LLM для анализа и декомпозиции сложных запросов.
"""

import logging
import time
from dataclasses import dataclass

from pydantic import BaseModel

from src.application.prompts.registry import PromptRegistry
from src.config.telemetry import traced_operation
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


@dataclass
class DecomposedQuery:
    """Результат декомпозиции и расширения запроса."""

    original: str
    expanded_queries: list[str]


class DecompositionResponse(BaseModel):
    """Модель ответа LLM для декомпозиции."""

    queries: list[str]


class QueryDecomposer:
    """Декомпозитор запросов.

    Разбивает сложные пользовательские запросы на атомарные подзапросы
    для более эффективного поиска информации.
    """

    def __init__(self, llm: LLMPort) -> None:
        self.llm = llm
        self._prompt_registry = PromptRegistry()
        self._cache: dict[str, tuple[DecomposedQuery, float]] = {}
        self._cache_ttl = 300

    async def decompose(
        self, query: str, history: list[dict[str, str]] | None = None
    ) -> DecomposedQuery:
        """Разбивает запрос за один LLM вызов с кэшированием."""
        cache_key = query.lower().strip()
        if history:
            # Include history length and last message content in cache key
            history_summary = f"{len(history)}"
            if history:
                history_summary += f":{history[-1].get('content', '')[:50]}"
            cache_key += f"|{history_summary}"

        if cache_key in self._cache:
            cached, timestamp = self._cache[cache_key]
            if time.time() - timestamp < self._cache_ttl:
                logger.info("Cache hit for query: %s", query[:50])
                return cached

        try:
            # Use separate model if configured (e.g. smaller model for decomposition)
            # But LLMClient generic interface doesn't support model override easily
            # per call unless we pass it. For now, assume generic LLM or we rely
            # on LLMClient internal config logic?
            # Actually generic LLMClient methods typically use self.model.
            # If we want specific model, we might need to instantiate separate
            # LLMClient or pass params?
            # The previous implementation in LLMClient used `settings.models.query_expansion`
            # if available.
            # We can't easily change model in generic port call.
            # We will use the default model for now, or we would need multiple
            # LLMClient instances injected.

            prompt = self._prompt_registry.format("decompose_expand", query=query)

            with traced_operation("query.decompose", {"query": query}):
                result = await self.llm.generate_structured(
                    messages=[{"role": "user", "content": prompt}],
                    response_model=DecompositionResponse,
                    max_tokens=500,
                    temperature=0.0
                )

                queries = result.queries[:3] if result and result.queries else [query]

            decomposed = DecomposedQuery(original=query, expanded_queries=queries)
            self._cache[cache_key] = (decomposed, time.time())
            return decomposed

        except Exception as e:
            logger.warning("Query decomposition failed: %s", e)
            return DecomposedQuery(original=query, expanded_queries=[query])
