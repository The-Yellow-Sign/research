"""Инструмент верификации ответа на галлюцинации.

Проверяет соответствие ответа контексту через LLM.
"""

import logging
from typing import TYPE_CHECKING, Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from src.config import settings

if TYPE_CHECKING:
    from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)

VERIFY_DESCRIPTION = (
    "Проверяет ответ на галлюцинации и соответствие контексту. "
    "Используй перед финальным ответом, если не уверен в качестве."
)


class VerifyAnswerTool(BaseTool):
    """Проверка ответа на галлюцинации и соответствие контексту."""

    name = "verify_answer"
    description = VERIFY_DESCRIPTION
    parameters = [
        ToolParameter(
            name="answer",
            type=ToolParameterType.STRING,
            description="Ответ для проверки",
            required=True,
        ),
        ToolParameter(
            name="context",
            type=ToolParameterType.STRING,
            description="Контекст (документы), на основе которого сгенерирован ответ",
            required=True,
        ),
    ]

    def __init__(self, llm: "LLMPort") -> None:
        """Инициализирует инструмент верификации."""
        self.llm = llm

    async def execute(
        self,
        answer: str,
        context: str,
        **kwargs: Any,
    ) -> ToolResult:
        """Проверяет ответ через LLM.

        Args:
            answer: Ответ для проверки.
            context: Контекст документов.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с результатом верификации.

        """
        try:
            prompt = f"""Контекст:
{context[: settings.agent_context_max_chars]}

Ответ для проверки:
{answer}

Проверь ответ и верни JSON с результатом."""

            from src.application.prompts.registry import PromptRegistry

            registry = PromptRegistry()
            system_prompt = registry.get("verify_system")

            model = settings.models.main
            response = await self.llm.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=500,
            )

            result_text = response.choices[0].message.content or ""

            logger.info("verify_answer: проверка завершена")

            return ToolResult(
                success=True,
                data=result_text,
            )

        except Exception as e:
            logger.error("verify_answer error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка верификации: {e}",
            )
