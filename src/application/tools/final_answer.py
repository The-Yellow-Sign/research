"""Инструмент финального ответа.

Терминальный инструмент — сигнализирует агенту завершить ReAct loop.
"""

import logging
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)

logger = logging.getLogger(__name__)

FINAL_ANSWER_DESCRIPTION = (
    "Финальный ответ пользователю. Используй когда у тебя достаточно информации для полного ответа."
)


class StructuredAnswer(BaseModel):
    """Валидированная структура ответа агента."""

    answer: str = Field(description="Полный ответ в Markdown")
    sources: list[str] = Field(default_factory=list, description="Источники [doc:N]")
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="Уверенность в ответе",
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
        ToolParameter(
            name="confidence",
            type=ToolParameterType.STRING,
            description="Уверенность: high, medium, low",
            required=False,
            default="medium",
        ),
    ]

    async def execute(
        self,
        answer: str,
        sources: list[str] | None = None,
        confidence: str = "medium",
        **kwargs: Any,
    ) -> ToolResult:
        """Форматирует и валидирует финальный ответ.

        Args:
            answer: Текст ответа.
            sources: Список источников.
            confidence: Уровень уверенности.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с валидированным ответом.

        """
        try:
            validated = StructuredAnswer(
                answer=answer,
                sources=sources or [],
                confidence=confidence if confidence in ("high", "medium", "low") else "medium",
            )
        except Exception as e:
            logger.warning("Validation failed, using raw answer: %s", e)
            validated = StructuredAnswer(answer=answer, sources=sources or [])

        formatted_answer = validated.answer

        if validated.sources:
            formatted_answer += "\n\n---\n**Источники:**\n"
            for i, source in enumerate(validated.sources, 1):
                formatted_answer += f"{i}. {source}\n"

        if validated.confidence == "low":
            formatted_answer += "\n\n> Ответ с низкой уверенностью — рекомендуется проверить."

        logger.info(
            "final_answer: ответ сформирован (%d символов, confidence=%s)",
            len(formatted_answer),
            validated.confidence,
        )

        return ToolResult(
            success=True,
            data=formatted_answer,
            metadata={
                "confidence": validated.confidence,
                "sources_count": len(validated.sources),
            },
        )
