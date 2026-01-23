"""Фабрика инструментов для агента.

Обеспечивает единую точку инициализации инструментов для API, CLI и оценки.
"""

import logging

from src.application.tools import (
    BaseTool,
    CodeExecTool,
    FinalAnswerTool,
    RagSearchTool,
    VerifyAnswerTool,
    WebSearchTool,
)
from src.domain.ports.llm import LLMPort
from src.domain.ports.search_engine import SearchEnginePort

logger = logging.getLogger(__name__)


def create_default_tools(
    search_engine: SearchEnginePort,
    llm_client: LLMPort,
    include_web: bool = True,
    include_code: bool = True,
) -> list[BaseTool]:
    """Создаёт стандартный набор инструментов для агента.

    Args:
        search_engine: Движок поиска для RagSearchTool.
        llm_client: LLM клиент для VerifyAnswerTool.
        include_web: Включить ли поиск в вебе.
        include_code: Включить ли выполнение кода.

    Returns:
        Список инициализированных инструментов.

    """
    tools: list[BaseTool] = [
        RagSearchTool(search_engine=search_engine),
        VerifyAnswerTool(llm=llm_client),
        FinalAnswerTool(),
    ]

    if include_web:
        tools.append(WebSearchTool())

    if include_code:
        tools.append(CodeExecTool())

    logger.info("Инициализировано инструментов: %d", len(tools))
    return tools
