"""DTO для исходящих ответов.

Содержит Pydantic-модели для ответов API:
- CitationMetrics — метрики качества цитирования
- Footnote — одна footnote-ссылка на источник
- ChatResponse — ответ для чат-взаимодействий
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from src.domain.models.response import SourceDoc


class CitationMetrics(BaseModel):
    """Метрики качества цитирования в ответе.

    Атрибуты:
        coverage: Доля предложений с [doc:X] (0.0-1.0).
        valid_citations: Список валидных doc IDs.
        invalid_removed: Количество удалённых галлюцинированных ссылок.

    """

    coverage: float
    valid_citations: list[int]
    invalid_removed: int = 0


class Footnote(BaseModel):
    """Одна footnote-ссылка на источник.

    Атрибуты:
        id: Порядковый номер ссылки в ответе ([1], [2], ...).
        source_type: Тип источника ("doc" или "web").
        title: Заголовок/путь документа или название страницы.
        source: Путь к файлу (для doc) или URL (для web).
        quote: Preview цитаты (~200 символов).
        service: Название сервиса (postgres, k8s, nginx) — только для doc.
        header_path: Путь к секции документа — только для doc.
        url: Полный URL — только для web.

    """

    id: int
    source_type: Literal["doc", "web"]
    title: str
    source: str
    quote: str
    service: str | None = None
    header_path: str | None = None
    url: str | None = None


class ChatResponse(BaseModel):
    """Модель ответа для чат-взаимодействий.

    Атрибуты:
        answer_type: Тип ответа ("final_answer" или "clarifying_question").
        answer: Сгенерированный ответ (в формате markdown с [doc:X]).
        sources: Список исходных документов, использованных для ответа.
        rewritten_query: Запрос после контекстуализации/переписывания.
        timings: Таймеры по этапам pipeline (опционально).
        citation_metrics: Метрики качества цитирования (опционально).
        footnotes: Список footnotes для раскрытия в UI (опционально).

    """

    model_config = ConfigDict(extra="forbid")

    answer_type: Literal["final_answer", "clarifying_question", "no_relevant_docs"]
    answer: str
    sources: list[SourceDoc]
    rewritten_query: str
    timings: dict[str, float] | None = None
    citation_metrics: CitationMetrics | None = None
    footnotes: list[Footnote] | None = None
    trace: dict[str, Any] | None = None
