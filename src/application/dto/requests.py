"""DTO для входящих запросов.

Содержит Pydantic-модели для запросов от пользователей:
- ChatRequest — запрос для чат-взаимодействий
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Модель запроса для чат-взаимодействий.

    Атрибуты:
        query: Вопрос или входной текст пользователя.
        history: История диалога как список словарей сообщений.
        filters: Опциональные фильтры поиска (например, {"service": "postgres"}).

    """

    model_config = ConfigDict(extra="forbid")

    query: str
    history: list[dict[str, str]] = Field(default_factory=list)
    filters: dict[str, Any] | None = None
