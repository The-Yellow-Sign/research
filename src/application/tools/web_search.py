"""Инструмент поиска в интернете через Tavily API.

Используется для актуальной информации, которой нет в локальной базе.
"""

import logging
import os
from typing import Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

WEB_SEARCH_DESCRIPTION = (
    "Поиск актуальной информации в интернете. "
    "Используй когда нужны свежие данные или информации нет в локальной базе."
)


class WebSearchTool(BaseTool):
    """Поиск актуальной информации в интернете через Tavily."""

    name = "web_search"
    description = WEB_SEARCH_DESCRIPTION
    parameters = [
        ToolParameter(
            name="query",
            type=ToolParameterType.STRING,
            description="Поисковый запрос (лучше на английском для точности)",
            required=True,
        ),
    ]

    def __init__(self, api_key: str | None = None) -> None:
        """Инициализирует инструмент веб-поиска."""
        self.api_key = api_key or TAVILY_API_KEY

    async def execute(self, query: str, **kwargs: Any) -> ToolResult:
        """Выполняет поиск в интернете.

        Args:
            query: Поисковый запрос.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с результатами поиска.

        """
        if not self.api_key:
            return ToolResult(
                success=False,
                data="",
                error="TAVILY_API_KEY не настроен. Добавь ключ в .env файл.",
            )

        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)
            response = client.search(query, max_results=5)

            results = response.get("results", [])
            if not results:
                return ToolResult(
                    success=True,
                    data="Результаты не найдены. Попробуй другой запрос.",
                )

            formatted = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                url = result.get("url", "")
                content = result.get("content", "")[:500]

                formatted.append(f"[{i}] {title}\nURL: {url}\n{content}")

            logger.info(
                "web_search: найдено %d результатов для '%s'",
                len(results),
                query[:50],
            )

            return ToolResult(
                success=True,
                data="\n---\n".join(formatted),
            )

        except ImportError:
            return ToolResult(
                success=False,
                data="",
                error="Библиотека tavily-python не установлена.",
            )
        except Exception as e:
            logger.error("web_search error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка веб-поиска: {e}",
            )
