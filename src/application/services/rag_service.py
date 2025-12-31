"""RAG-сервис — слой бизнес-логики.

Фасад для RAG-пайплайна, делегирующий работу компонентам Application Layer:
- QueryProcessor — главный оркестратор
- DocumentAnalyzer — анализ документов
- QueryExpander — расширение запросов

Сохранён для обратной совместимости с существующим кодом.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any

from src.application.dto import ChatRequest, ChatResponse
from src.application.use_cases import QueryProcessor
from src.domain.models.response import SourceDoc
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.search.engine import SearchEngine

logger = logging.getLogger(__name__)


class RAGService:
    """Основной RAG-сервис (Фасад).

    Делегирует обработку запросов QueryProcessor из Application Layer.
    Сохранён для обратной совместимости с API и CLI.

    Атрибуты:
        llm_client: Клиент для работы с LLM.
        search_engine: Экземпляр SearchEngine для гибридного поиска.
        query_processor: Оркестратор RAG-пайплайна.

    """

    def __init__(
        self,
        search_engine: SearchEngine | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        """Инициализация RAG-сервиса.

        Args:
            search_engine: Опциональный экземпляр SearchEngine.
            llm_client: Опциональный LLM-клиент.

        """
        logger.info("Инициализация RAGService...")

        if search_engine is not None:
            self.search_engine = search_engine
            logger.info("Используется переданный SearchEngine")
        else:
            logger.info("Создание нового SearchEngine...")
            self.search_engine = SearchEngine()

        if llm_client is not None:
            self.llm_client = llm_client
            logger.info("Используется переданный LLM-клиент")
        else:
            self.llm_client = LLMClient()
            logger.info("Создан новый LLM-клиент")


        self.query_processor = QueryProcessor(
            llm=self.llm_client,
            search_engine=self.search_engine,
        )

        logger.info("RAGService инициализирован")

    async def process_query(self, request: ChatRequest) -> ChatResponse:
        """Обрабатывает запрос через полный RAG-пайплайн.

        Делегирует QueryProcessor.

        Args:
            request: ChatRequest с запросом, историей и фильтрами.

        Returns:
            ChatResponse с ответом, источниками и переписанным запросом.

        """
        return await self.query_processor.process(request)

    async def process_query_stream(
        self,
        request: ChatRequest,
    ) -> AsyncIterator[str]:
        """Streaming-версия process_query.

        Делегирует QueryProcessor.

        Args:
            request: ChatRequest с запросом.

        Yields:
            Токены ответа по мере генерации.

        """
        async for token in self.query_processor.process_stream(request):
            yield token



    def _build_context_xml(self, search_results: list[dict[str, Any]]) -> str:
        """Формирует XML-контекст (legacy, делегирует QueryProcessor)."""
        return self.query_processor._build_context_xml(search_results)

    def _build_sources(self, search_results: list[dict[str, Any]]) -> list[SourceDoc]:
        """Конвертирует результаты в DTO (legacy, делегирует QueryProcessor)."""
        return self.query_processor._build_sources(search_results)
