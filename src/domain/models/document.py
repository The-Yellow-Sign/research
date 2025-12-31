"""Доменные модели документов.

Содержит Value Objects для работы с документами:
- ExtractedBlock — извлечённый блок (код или таблица)
- generate_parent_id — генерация уникального ID для parent-документа
"""

import hashlib
from dataclasses import dataclass


@dataclass
class ExtractedBlock:
    """Извлечённый специальный блок (код или таблица).

    Атрибуты:
        block_type: Тип блока ("code" или "table").
        content: Содержимое блока.
        language: Язык программирования (для code блоков).
        snippet: Краткий превью содержимого.
    """

    block_type: str
    content: str
    language: str | None = None
    snippet: str | None = None


def generate_parent_id(filename: str, header_path: str) -> str:
    """Генерирует уникальный parent ID через SHA256-хэш.

    Args:
        filename: Имя исходного файла.
        header_path: Путь в иерархии заголовков (breadcrumb).

    Returns:
        SHA256-хэш строки "filename::header_path".

    """
    content = f"{filename}::{header_path}"
    return hashlib.sha256(content.encode()).hexdigest()
