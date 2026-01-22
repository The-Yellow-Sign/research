"""Инструмент поиска по локальной базе знаний.

Обёртка над SearchEngine для использования в агентном режиме.
"""

import logging
import time
from typing import Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from src.config import settings
from src.domain.ports.search_engine import SearchEnginePort

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

    def __init__(self, search_engine: SearchEnginePort) -> None:
        """Инициализирует инструмент поиска."""
        self.search_engine = search_engine

    async def execute(
        self,
        query: str,
        top_k: int = 5,
        **kwargs: Any,
    ) -> ToolResult:
        """Выполняет поиск по базе знаний."""
        try:
            start_retrieve = time.perf_counter()
            candidates = await self.search_engine.retrieve_candidates(query=query)
            retrieve_sec = time.perf_counter() - start_retrieve

            if not candidates:
                return ToolResult(
                    success=True,
                    data=(
                        "Документы не найдены. "
                        "Попробуй переформулировать запрос или использовать web_search."
                    ),
                    metadata={
                        "timings": {
                            "retrieve": retrieve_sec,
                            "rerank": 0.0,
                        }
                    },
                )

            start_rerank = time.perf_counter()
            results = self.search_engine.rerank_candidates(
                query=query, candidates=candidates, top_k=top_k
            )
            rerank_sec = time.perf_counter() - start_rerank

            formatted = []
            documents_with_meta = []
            for i, doc in enumerate(results, 1):
                service = doc.get("service", "unknown")
                header = doc.get("header_path", "")
                source_file = doc.get("source", doc.get("source_file", "unknown"))
                content = doc.get("raw_content", "")[: settings.rag_search_content_limit]
                score = doc.get("score", 0)

                documents_with_meta.append(
                    {
                        **doc,
                        "source_type": "doc",
                        "source_name": source_file,
                        "quote_preview": content[:200] if content else "",
                    }
                )

                formatted.append(
                    f"[{i}] {source_file} ({service})\n"
                    f"Header: {header}\n"
                    f"Score: {score:.2f}\n"
                    f"{content}\n"
                )

            logger.info(
                "rag_search: найдено %d документов для '%s' (retrieve=%.2fs, rerank=%.2fs)",
                len(results),
                query[:50],
                retrieve_sec,
                rerank_sec,
            )

            return ToolResult(
                success=True,
                data="\n---\n".join(formatted),
                metadata={
                    "timings": {
                        "retrieve": retrieve_sec,
                        "rerank": rerank_sec,
                    },
                    "documents": documents_with_meta,
                    "source_type": "doc",
                },
            )

        except Exception as e:
            duration = time.perf_counter() - start_retrieve
            logger.error("rag_search error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка поиска: {e}",
                metadata={
                    "timings": {
                        "retrieve": duration,
                        "rerank": 0.0,
                    }
                },
            )
