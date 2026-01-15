"""DTO для исходящих ответов.

Содержит Pydantic-модели для ответов API:
- CitationMetrics — метрики качества цитирования
- Footnote — одна footnote-ссылка на источник
- ChatResponse — ответ для чат-взаимодействий
"""

from typing import Literal

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
        doc_id: ID документа ([doc:X] в тексте ответа).
        service: Название сервиса (postgres, k8s, nginx).
        title: Заголовок/путь документа.
        source_file: Путь к исходному файлу.

    """

    doc_id: int
    service: str
    title: str
    source_file: str
    quote: str


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


