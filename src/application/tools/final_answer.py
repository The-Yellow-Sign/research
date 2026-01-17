"""Инструмент финального ответа.

Терминальный инструмент — сигнализирует агенту завершить ReAct loop.
"""

import logging
from typing import Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)

logger = logging.getLogger(__name__)

FINAL_ANSWER_DESCRIPTION = (
    "Финальный ответ пользователю. "
    "Используй когда у тебя достаточно информации для полного ответа."
)


class FinalAnswerTool(BaseTool):
    """Формирует и возвращает финальный ответ пользователю."""

    name = "final_answer"
    description = FINAL_ANSWER_DESCRIPTION
    parameters = [
        ToolParameter(
            name="answer",
            type=ToolParameterType.STRING,
            description="Полный ответ пользователю в формате Markdown",
            required=True,
        ),
        ToolParameter(
            name="sources",
            type=ToolParameterType.ARRAY,
            description="Список использованных источников (опционально)",
            required=False,
            default=[],
        ),
    ]

    async def execute(
        self,
        answer: str,
        sources: list[str] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Форматирует финальный ответ.

        Args:
            answer: Текст ответа.
            sources: Список источников.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с финальным ответом.

        """
        formatted_answer = answer

        if sources:
            formatted_answer += "\n\n---\n**Источники:**\n"
            for i, source in enumerate(sources, 1):
                formatted_answer += f"{i}. {source}\n"

        logger.info(
            "final_answer: ответ сформирован (%d символов)",
            len(formatted_answer),
        )

        return ToolResult(
            success=True,
            data=formatted_answer,
        )
