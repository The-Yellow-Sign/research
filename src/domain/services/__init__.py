"""Доменные сервисы.

Содержит чистую бизнес-логику без внешних зависимостей:
- chunking.py — логика разбиения документов на чанки
- metadata_extractor.py — извлечение метаданных через GLiNER/regex
"""

from src.domain.services.chunking import (
    build_header_path,
    build_vector_text,
    extract_path_metadata,
    infer_service_from_path,
    parse_frontmatter,
    process_markdown_ast,
)

__all__ = [
    "parse_frontmatter",
    "infer_service_from_path",
    "extract_path_metadata",
    "build_header_path",
    "process_markdown_ast",
    "build_vector_text",
]
