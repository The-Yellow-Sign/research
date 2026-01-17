"""Инструмент поиска по локальной базе знаний.

Обёртка над SearchEngine для использования в агентном режиме.
"""

import logging
from typing import TYPE_CHECKING, Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)

if TYPE_CHECKING:
    from src.infrastructure.search.engine import SearchEngine

logger = logging.getLogger(__name__)

RAG_SEARCH_DESCRIPTION = (
    "Поиск по локальной базе знаний DevOps. "
    "Используй для вопросов о конфигурациях, настройке сервисов, troubleshooting."
)


class RagSearchTool(BaseTool):
    """Поиск по локальной базе знаний DevOps документации."""

    name = "rag_search"
    description = RAG_SEARCH_DESCRIPTION
    parameters = [
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Поисковый запрос на русском или английском",
            required=True,
        ),
        ToolParameter(
            name="top_k",
            type=ToolParameterType.INTEGER,
            description="Количество результатов (по умолчанию 5)",
            required=False,
            default=5,
        ),
    ]

    def __init__(self, search_engine: "SearchEngine") -> None:
        """Инициализирует инструмент поиска."""
        self.search_engine = search_engine

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        **kwargs: Any,
    ) -> ToolResult:
        """Выполняет поиск по базе знаний.

        Args:
            query: Поисковый запрос.
            top_k: Количество результатов.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с найденными документами.

        """
        try:
            results = await self.search_engine.hybrid_search(query=query)

            if not results:
                return ToolResult(
                    success=True,
                    data=(
                        "Документы не найдены. "
                        "Попробуй переформулировать запрос или использовать web_search."
                    ),
                )

            formatted = []
            for i, doc in enumerate(results, 1):
                service = doc.get("service", "unknown")
                header = doc.get("header_path", "")
                content = doc.get("raw_content", "")[:1500]
                score = doc.get("final_score", 0)

                formatted.append(
                    f"[{i}] {service} | {header}\n"
                    f"Score: {score:.2f}\n"
                    f"{content}\n"
                )

            logger.info(
                "rag_search: найдено %d документов для '%s'",
                len(results),
                query[:50],
            )

            return ToolResult(
                success=True,
                data="\n---\n".join(formatted),
            )

        except Exception as e:
            logger.error("rag_search error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка поиска: {e}",
            )
