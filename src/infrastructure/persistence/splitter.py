"""Модуль разбиения Markdown-документов на чанки.

Реализует паттерн Parent-Document Retrieval:
- Разбиение по markdown-заголовкам (parent = секция документа)
- Извлечение блоков кода и таблиц через AST-парсинг (Marko GFM)
- Создание children-чанков с обогащённым контекстом для векторного поиска
- Опциональное LLM-обогащение метаданных при индексации

Использует доменные сервисы из src.domain.services.chunking.
"""

import logging
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

from src.config import CHUNK_OVERLAP, CHUNK_SIZE, MIN_CHUNK_CHARS, SOURCE_DIR
from src.domain.models.document import ExtractedBlock, generate_parent_id
from src.domain.services.chunking import (
    build_header_path,
    build_vector_text,
    infer_service_from_path,
    parse_frontmatter,
    process_markdown_ast,
)
from src.domain.services.metadata_extractor import (
    extract_metadata,
    extract_metadata_with_llm_fallback,
)

logger = logging.getLogger(__name__)


HEADERS_TO_SPLIT: list[tuple[str, str]] = [
    ("#", "header_1"),
    ("##", "header_2"),
    ("###", "header_3"),
]

_markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=HEADERS_TO_SPLIT)
_text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=CHUNK_SIZE,
    chunk_overlap=CHUNK_OVERLAP,
)


__all__ = [
    "ExtractedBlock",
    "generate_parent_id",
    "parse_frontmatter",
    "infer_service_from_path",
    "build_header_path",
    "process_markdown_ast",
    "build_vector_text",
    "process_files",
    "process_specific_files",
    "process_files_async",
    "process_specific_files_async",
]


def process_files() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает все markdown-файлы в директории SOURCE_DIR.

    Синхронная версия без LLM-обогащения метаданных.
    Использует GLiNER + regex для извлечения entities.

    Returns:
        Кортеж (parents, children) со списками документов.

    """
    if not SOURCE_DIR.is_dir():
        logger.warning("Исходная директория не найдена: %s", SOURCE_DIR)
        return [], []

    files = list(SOURCE_DIR.glob("**/*.md"))
    logger.info("Найдено %d markdown-файлов", len(files))

    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for filepath in files:
        parents, children = _process_single_file(filepath)
        all_parents.extend(parents)
        all_children.extend(children)

    return all_parents, all_children


def process_specific_files(
    filepaths: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает указанный список markdown-файлов.

    Args:
        filepaths: Список путей к файлам для обработки.

    Returns:
        Кортеж (parents, children) со списками документов.

    """
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for filepath in filepaths:
        if not filepath.exists():
            logger.warning("Файл не найден: %s", filepath)
            continue

        parents, children = _process_single_file(filepath)
        all_parents.extend(parents)
        all_children.extend(children)

    return all_parents, all_children


def _process_single_file(filepath: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает один markdown-файл.

    Извлекает frontmatter, определяет сервис, разбивает по заголовкам
    и создаёт parent/children документы.

    Args:
        filepath: Путь к markdown-файлу.

    Returns:
        Кортеж (parents, children) для данного файла.

    """
    try:
        filename = str(filepath.relative_to(SOURCE_DIR))
    except ValueError:
        filename = filepath.name

    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as e:
        logger.error("Ошибка чтения файла %s: %s", filename, e)
        return [], []

    file_meta, content = parse_frontmatter(content)

    service = file_meta.get("service")
    if not service:
        service = infer_service_from_path(filepath)
    if not service:
        service = "general"

    splits = _markdown_splitter.split_text(content)

    if not splits and content.strip():
        splits = [Document(page_content=content, metadata={})]

    for split in splits:
        parent, section_children = _process_section(split, filename, service)
        if parent:
            parents.append(parent)
        children.extend(section_children)

    return parents, children


def _process_section(
    split: Document,
    filename: str,
    service: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Обрабатывает одну markdown-секцию (уровень parent).

    Создаёт parent-документ с полным текстом секции и metadata,
    затем разбивает на children-чанки для индексации.

    Args:
        split: Document объект с текстом секции и метаданными заголовков.
        filename: Имя исходного файла.
        service: Определённое название сервиса.

    Returns:
        Кортеж (parent_doc, list_of_children).

    """
    section_text = split.page_content.strip()
    if not section_text:
        return None, []

    header_path = build_header_path({**split.metadata, "source_file": filename})
    parent_id = generate_parent_id(filename, header_path)

    mentions = extract_metadata(section_text)

    parent = {
        "id": parent_id,
        "full_text": section_text,
        "metadata": {
            "source_file": filename,
            "service": service,
            "header_path": header_path,
            **split.metadata,
            "mentions": mentions,
        },
    }

    children = _create_children(
        section_text=section_text,
        parent_id=parent_id,
        filename=filename,
        service=service,
        header_path=header_path,
        metadata=split.metadata,
    )

    return parent, children


def _create_children(
    section_text: str,
    parent_id: str,
    filename: str,
    service: str,
    header_path: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Создаёт children-документы из текста секции.

    Извлекает блоки кода и таблицы через AST-парсинг,
    затем разбивает оставшийся текст на чанки заданного размера.

    Args:
        section_text: Полный текст секции.
        parent_id: Идентификатор parent-документа.
        filename: Имя исходного файла.
        service: Название сервиса.
        header_path: Breadcrumb-путь по заголовкам.
        metadata: Дополнительные метаданные из заголовков.

    Returns:
        Список children-документов для индексации.

    """
    children: list[dict[str, Any]] = []

    text_with_placeholders, blocks = process_markdown_ast(section_text)

    base_meta = {
        "source_file": filename,
        "service": service,
        "header_path": header_path,
        "parent_id": parent_id,
        **metadata,
    }

    for block in blocks:
        if len(block.content) < MIN_CHUNK_CHARS:
            continue

        if block.block_type == "code":
            code_context = f"{block.language} code"
            vector_text = build_vector_text(
                service, header_path, f"{code_context}: {block.content[:500]}"
            )

            children.append(
                {
                    "text": block.content,
                    "vector_text": vector_text,
                    "raw_content": f"```{block.language}\n{block.content}\n```",
                    "chunk_type": "code",
                    "metadata": {**base_meta, "code_language": block.language},
                }
            )

        elif block.block_type == "table":
            table_context = "markdown table"
            vector_text = build_vector_text(
                service, header_path, f"{table_context}: {block.content[:500]}"
            )

            children.append(
                {
                    "text": block.content,
                    "vector_text": vector_text,
                    "raw_content": block.content,
                    "chunk_type": "table",
                    "metadata": base_meta,
                }
            )

    text_chunks = _text_splitter.split_text(text_with_placeholders)

    for chunk_text in text_chunks:
        if len(chunk_text) < MIN_CHUNK_CHARS:
            continue

        vector_text = build_vector_text(service, header_path, chunk_text)

        children.append(
            {
                "text": chunk_text,
                "vector_text": vector_text,
                "raw_content": chunk_text,
                "chunk_type": "text",
                "metadata": base_meta,
            }
        )

    return children


async def process_files_async() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает все markdown-файлы с LLM-обогащением метаданных.

    Асинхронная версия с вызовом LLM для улучшения качества
    извлечения entities при слабых результатах GLiNER/regex.

    Returns:
        Кортеж (parents, children) со списками документов.

    """
    if not SOURCE_DIR.is_dir():
        logger.warning("Исходная директория не найдена: %s", SOURCE_DIR)
        return [], []

    files = list(SOURCE_DIR.glob("**/*.md"))
    logger.info("Найдено %d markdown-файлов (async with LLM)", len(files))

    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for filepath in files:
        parents, children = await _process_single_file_async(filepath)
        all_parents.extend(parents)
        all_children.extend(children)

    return all_parents, all_children


async def process_specific_files_async(
    filepaths: list[Path],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает указанные файлы с LLM-обогащением метаданных.

    Args:
        filepaths: Список путей к файлам для обработки.

    Returns:
        Кортеж (parents, children) со списками документов.

    """
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for filepath in filepaths:
        if not filepath.exists():
            logger.warning("Файл не найден: %s", filepath)
            continue

        parents, children = await _process_single_file_async(filepath)
        all_parents.extend(parents)
        all_children.extend(children)

    return all_parents, all_children


async def _process_single_file_async(
    filepath: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Обрабатывает один файл с LLM-обогащением метаданных.

    Args:
        filepath: Путь к markdown-файлу.

    Returns:
        Кортеж (parents, children) для данного файла.

    """
    try:
        filename = str(filepath.relative_to(SOURCE_DIR))
    except ValueError:
        filename = filepath.name

    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []

    try:
        content = filepath.read_text(encoding="utf-8")
    except OSError as e:
        logger.error("Ошибка чтения файла %s: %s", filename, e)
        return [], []

    file_meta, content = parse_frontmatter(content)

    service = file_meta.get("service")
    if not service:
        service = infer_service_from_path(filepath)
    if not service:
        service = "general"

    splits = _markdown_splitter.split_text(content)

    if not splits and content.strip():
        splits = [Document(page_content=content, metadata={})]

    for split in splits:
        parent, section_children = await _process_section_async(split, filename, service)
        if parent:
            parents.append(parent)
        children.extend(section_children)

    return parents, children


async def _process_section_async(
    split: Document,
    filename: str,
    service: str,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Обрабатывает секцию с LLM-обогащённым извлечением entities.

    При слабых результатах GLiNER/regex автоматически
    вызывает LLM для качественного извлечения метаданных.

    Args:
        split: Document объект с текстом секции.
        filename: Имя исходного файла.
        service: Определённое название сервиса.

    Returns:
        Кортеж (parent_doc, list_of_children).

    """
    section_text = split.page_content.strip()
    if not section_text:
        return None, []

    header_path = build_header_path({**split.metadata, "source_file": filename})
    parent_id = generate_parent_id(filename, header_path)

    mentions = await extract_metadata_with_llm_fallback(section_text)

    parent = {
        "id": parent_id,
        "full_text": section_text,
        "metadata": {
            "source_file": filename,
            "service": service,
            "header_path": header_path,
            **split.metadata,
            "mentions": mentions,
        },
    }

    children = _create_children(
        section_text=section_text,
        parent_id=parent_id,
        filename=filename,
        service=service,
        header_path=header_path,
        metadata=split.metadata,
    )

    return parent, children
