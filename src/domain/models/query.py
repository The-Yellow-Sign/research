"""Доменные модели запросов.

Содержит Structured Output модели для LLM:
- QueryExpansion — результат расширения запроса
- DocAnalysis — результат анализа релевантности документа
"""

from pydantic import BaseModel, Field


class QueryExpansion(BaseModel):
    """Результат расширения запроса.

    Используется LLM для генерации вариаций запроса,
    улучшающих полноту поиска (Query Expansion).

    Атрибуты:
        rewritten_query: Основной запрос, уточненный по истории и контексту.
        variations: 2-3 альтернативных формулировки.

    """

    rewritten_query: str = Field(
        ...,
        description="Основной запрос, уточненный по истории и контексту.",
    )
    variations: list[str] = Field(
        ...,
        description="2-3 альтернативных формулировки (синонимы, технические термины, коды ошибок).",
        min_length=2,
        max_length=4,
    )


class DocAnalysis(BaseModel):
    """Structured Output для анализа релевантности документа.

    Используется LLM для оценки релевантности и извлечения ключевой информации.
    Обеспечивает Context Compression перед генерацией финального ответа.

    Атрибуты:
        relevance_score: Оценка релевантности от 0 (мусор) до 5 (прямой ответ).
        summary: Сжатая выжимка полезной информации для запроса.
        reasoning: Краткое объяснение выставленной оценки.

    """

    relevance_score: int = Field(
        ...,
        ge=0,
        le=5,
        description="Оценка релевантности от 0 (мусор) до 5 (прямой ответ)",
    )
    summary: str = Field(
        ...,
        description=(
            "Краткая выжимка из документа, содержащая ТОЛЬКО информацию, "
            "полезную для ответа на вопрос пользователя."
        ),
    )
    reasoning: str = Field(
        ...,
        description="Краткое объяснение оценки",
        max_length=500,
    )
