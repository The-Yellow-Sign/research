"""Доменные сервисы.

Содержит чистую бизнес-логику без внешних зависимостей:
- chunking.py — логика разбиения документов на чанки
"""

from src.domain.services.chunking import (
    KNOWN_SERVICES,
    SERVICE_ALIASES,
    build_header_path,
    build_vector_text,
    infer_service_from_path,
    parse_frontmatter,
    process_markdown_ast,
)

__all__ = [
    "KNOWN_SERVICES",
    "SERVICE_ALIASES",
    "parse_frontmatter",
    "infer_service_from_path",
    "build_header_path",
    "process_markdown_ast",
    "build_vector_text",
]
