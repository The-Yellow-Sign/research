"""Модели данных для агента.

DTO и Pydantic-модели для AgentController.
"""

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from src.application.dto.responses import CitationMetrics


class AgentEventType(str, Enum):
    """Типы событий для streaming."""

    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ANSWER = "answer"
    ERROR = "error"


@dataclass
class AgentResponse:
    """Финальный ответ агента."""

    answer: str
    sources: list[str]
    steps: int
    total_time_sec: float
    trace: dict[str, Any] | None = None
    footnotes: list[Any] = field(default_factory=list)
    citation_metrics: CitationMetrics | None = None
    retrieved_docs: list[Any] = field(default_factory=list)


@dataclass
class AgentEvent:
    """Событие агента для streaming."""

    type: AgentEventType
    content: str = ""
    tool: str | None = None
    params: dict[str, Any] | None = None
    sources: list[str] = field(default_factory=list)
    agent_response: AgentResponse | None = None

    def to_dict(self) -> dict[str, Any]:
        """Конвертирует событие в словарь."""
        return {
            "type": self.type.value,
            "content": self.content,
            "tool": self.tool,
            "params": self.params,
            "sources": self.sources,
        }

    def json(self) -> str:
        """Сериализует событие в JSON."""
        return json.dumps(self.to_dict(), ensure_ascii=False)


class AgentAction(str, Enum):
    """Доступные действия агента."""

    RAG_SEARCH = "rag_search"
    WEB_SEARCH = "web_search"
    CODE_EXEC = "code_exec"
    FINAL_ANSWER = "final_answer"
    CLARIFYING_QUESTION = "clarifying_question"

    TOKEN_LIMIT = "token_limit_error"  # noqa: S105
    INVALID_SCHEMA = "invalid_schema_error"


class AgentThought(BaseModel):
    """Структура мысли агента."""

    thought: str
    action: AgentAction | str
    params: dict[str, Any] = {}


class AgentDecision(BaseModel):
    """Модель решения агента для Structured Output."""

    thought: str = Field(
        description="Твои рассуждения (Chain of Thought). Почему ты выбираешь этот инструмент?"
    )
    tool_name: AgentAction = Field(description="Название инструмента для выполнения")
    params: dict[str, Any] = Field(description="Параметры для инструмента")


class AgentReflection(BaseModel):
    """Модель рефлексии для проверки качества ответа."""

    is_approved: bool = Field(description="Утвержден ли ответ пользователя?")
    thought: str = Field(description="Твои рассуждения (Chain of Thought)")
    critique: str = Field(description="Критический отзыв, если ответ не утвержден")
