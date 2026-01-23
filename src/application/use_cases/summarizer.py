"""Use Case: Суммаризация документов.

Отвечает за:
- Сжатие отдельных документов
- Batch summarization
"""

import logging

from pydantic import BaseModel

from src.application.prompts.registry import PromptRegistry
from src.config import settings
from src.domain.ports.llm import LLMPort

logger = logging.getLogger(__name__)


class BatchSummaryResponse(BaseModel):
    """Модель ответа для batch summarization."""

    summaries: list[str]


class Summarizer:
    """Сервис суммаризации документов."""

    def __init__(self, llm: LLMPort) -> None:
        self.llm = llm
        self._prompt_registry = PromptRegistry()

    async def summarize_document(self, content: str) -> str:
        """Сжимает текст документа, сохраняя ключевую информацию."""
        if not content:
            return ""

        try:
            prompt = (
                f"{self._prompt_registry.get('summary_prompt')}\n\n"
                f"Текст:\n---\n{content}\n---\nСжатый текст:"
            )

            return await self.llm.generate(prompt, max_tokens=500)

        except Exception as e:
            logger.warning("Ошибка суммаризации (возвращаем оригинал): %s", e)
            return content

    async def summarize_batch(self, contents: list[str]) -> list[str]:
        """Batch summarization — сжимает несколько документов за один LLM вызов."""
        if not contents:
            return []

        docs_xml = "\n".join(
            [
                f"<doc id='{i}'>{content[: settings.summary_max_chars_per_doc]}</doc>"
                for i, content in enumerate(contents, 1)
            ]
        )

        try:
            messages = [
                {
                    "role": "system",
                    "content": self._prompt_registry.get("batch_summary_prompt"),
                },
                {"role": "user", "content": docs_xml},
            ]

            result = await self.llm.generate_structured(
                messages=messages,
                response_model=BatchSummaryResponse,
                max_tokens=2500,
                temperature=0.3
            )

            if result and result.summaries:
                if len(result.summaries) == len(contents):
                    return result.summaries

                # Fallback if counts mismatch
                summaries = list(result.summaries)
                for i in range(len(summaries), len(contents)):
                    summaries.append(contents[i][: settings.summary_max_chars_per_doc])
                return summaries

            return contents

        except Exception as e:
            logger.warning("Batch summarization failed, returning originals: %s", e)
            return contents
