"""Инструмент поиска в интернете через Tavily API.

Используется для актуальной информации, которой нет в локальной базе.
"""

import logging
import time
from typing import Any

from tavily import TavilyClient

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from src.config import settings

logger = logging.getLogger(__name__)

TAVILY_API_KEY = settings.tavily_api_key.get_secret_value()

WEB_SEARCH_DESCRIPTION = (
    "Поиск актуальной информации в интернете. "
    "Используй когда нужны свежие данные или информации нет в локальной базе."
)


def _extract_domain(url: str) -> str:
    """Извлекает domain из URL."""
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc or url
    except Exception:
        return url


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
        try:
            start_time = time.perf_counter()
            if not self.api_key:
                return ToolResult(
                    success=False,
                    data="",
                    error="TAVILY_API_KEY не настроен. Добавь ключ в .env файл.",
                )

            client = TavilyClient(api_key=self.api_key)
            response = client.search(query, max_results=5)
            duration = time.perf_counter() - start_time

            results = response.get("results", [])
            if not results:
                return ToolResult(
                    success=True,
                    data="Результаты не найдены. Попробуй другой запрос.",
                    metadata={"timings": {"web_search": duration}},
                )

            formatted = []
            web_sources = []
            for i, result in enumerate(results, 1):
                title = result.get("title", "")
                url = result.get("url", "")
                content = result.get("content", "")[:500]
                domain = _extract_domain(url)

                web_sources.append(
                    {
                        "source_type": "web",
                        "source_name": domain,
                        "title": title,
                        "url": url,
                        "quote_preview": content[:200] if content else "",
                    }
                )

                formatted.append(f"[{i}] {title} ({domain})\nURL: {url}\n{content}")

            logger.info(
                "web_search: найдено %d результатов для '%s' (%.2fs)",
                len(results),
                query[:50],
                duration,
            )

            return ToolResult(
                success=True,
                data="\n---\n".join(formatted),
                metadata={
                    "timings": {"web_search": duration},
                    "web_sources": web_sources,
                    "source_type": "web",
                },
            )

        except ImportError:
            return ToolResult(
                success=False,
                data="",
                error="Библиотека tavily-python не установлена.",
            )
        except Exception as e:
            duration = time.perf_counter() - start_time
            logger.error("web_search error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка веб-поиска: {e}",
                metadata={"timings": {"web_search": duration}},
            )
