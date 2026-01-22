"""Доменные модели ответов.

Содержит Value Objects для представления результатов:
- SourceDoc — исходный документ, использованный для генерации ответа
"""

from pydantic import BaseModel


class SourceDoc(BaseModel):
    """Представляет исходный документ, использованный для генерации ответа.

    Атрибуты:
        doc_id: ID документа для цитирования [doc:X].
        rank: Позиция в ранжированных результатах (начиная с 1).
        score: Оценка релевантности от реранкера (0.0-1.0).
        service: Название сервиса/технологии (например, 'postgres', 'nginx').
        source_file: Путь к исходному файлу.
        header_path: Иерархический путь из markdown-заголовков.
        content: Полный текст документа.

    """

    doc_id: int
    rank: int
    score: float
    service: str
    source_file: str
    header_path: str
    content: str
