"""DTO для исходящих ответов.

Содержит Pydantic-модели для ответов API:
- ChatResponse — ответ для чат-взаимодействий
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from src.domain.models.response import SourceDoc


class ChatResponse(BaseModel):
    """Модель ответа для чат-взаимодействий.

    Атрибуты:
        answer_type: Тип ответа ("final_answer" или "clarifying_question").
        answer: Сгенерированный ответ (в формате markdown).
        sources: Список исходных документов, использованных для ответа.
        rewritten_query: Запрос после контекстуализации/переписывания.
        timings: Таймеры по этапам pipeline (опционально).

    """

    model_config = ConfigDict(extra="forbid")

    answer_type: Literal["final_answer", "clarifying_question", "no_relevant_docs"]
    answer: str
    sources: list[SourceDoc]
    rewritten_query: str
    timings: dict[str, float] | None = None
