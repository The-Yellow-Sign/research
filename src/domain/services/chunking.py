"""Доменный сервис чанкинга документов.

Содержит чистую бизнес-логику разбиения markdown-документов на чанки:
- Извлечение YAML frontmatter
- Определение сервиса по структуре пути (DDD-подход)
- Построение breadcrumb-путей по заголовкам
- AST-парсинг markdown через Marko
- Создание обогащённого текста для векторных эмбеддингов
"""

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from marko.block import FencedCode
from marko.ext.gfm import gfm
from marko.ext.gfm.elements import Table

from src.domain.models.document import ExtractedBlock

logger = logging.getLogger(__name__)


_marko_parser = gfm

_SKIP_FOLDERS: set[str] = {
    "docs",
    "documentation",
    "wiki",
    "examples",
    "samples",
    "src",
    "lib",
    "pkg",
    ".",
    "..",
}


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Извлекает YAML frontmatter из начала markdown-документа.

    Frontmatter — это YAML-блок в начале файла между тройными дефисами.
    Содержит метаданные документа: title, tags, service и т.д.

    Args:
        text: Полный текст markdown-документа.

    Returns:
        Кортеж из словаря frontmatter и текста без frontmatter.
        При отсутствии frontmatter возвращает пустой словарь.

    """
    pattern = r"^---\n(.*?)\n---\n"
    match = re.match(pattern, text, re.DOTALL)

    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            content = text[match.end() :].strip()
            return frontmatter, content
        except yaml.YAMLError as e:
            logger.warning("Ошибка парсинга frontmatter: %s", e)

    return {}, text.strip()


def infer_service_from_path(filepath: Path, source_dir: Path | None = None) -> str | None:
    """Определяет название сервиса по структуре пути файла.

    Использует DDD-подход: первая не-служебная папка в пути
    считается названием bounded context (сервиса).

    Служебные папки (docs, src, lib, etc.) пропускаются.

    Args:
        filepath: Путь к файлу документа.
        source_dir: Корневая директория источников для вычисления relative path.

    Returns:
        Нормализованное название сервиса (lowercase, дефисы) или None.

    """
    if source_dir:
        try:
            relative = filepath.relative_to(source_dir)
            parts = list(relative.parent.parts)
        except ValueError:
            parts = list(filepath.parent.parts)
    else:
        parts = list(filepath.parent.parts)

    for part in parts:
        if part.lower() not in _SKIP_FOLDERS:
            return part.lower().replace("_", "-")

    return None


_DOC_TYPE_HINTS: dict[str, str] = {
    "troubleshoot": "troubleshooting",
    "debug": "troubleshooting",
    "install": "installation",
    "setup": "installation",
    "deploy": "deployment",
    "config": "configuration",
    "api": "api_reference",
    "readme": "overview",
    "guide": "tutorial",
    "tutorial": "tutorial",
    "example": "examples",
}


def extract_path_metadata(filepath: Path, source_dir: Path | None = None) -> dict[str, Any]:
    """Извлекает метаданные из структуры пути файла.

    Анализирует путь для определения репозитория, типа документа
    и категории на основе имени файла и названий папок.

    Args:
        filepath: Путь к файлу документа.
        source_dir: Корневая директория источников.

    Returns:
        Словарь с ключами: filename, path_parts, repo, doc_type, category.

    """
    if source_dir:
        try:
            relative = filepath.relative_to(source_dir)
        except ValueError:
            relative = filepath
    else:
        relative = filepath

    parts = list(relative.parts)
    filename = parts[-1].replace(".md", "").replace(".MD", "")
    folder_parts = parts[:-1]

    metadata: dict[str, Any] = {
        "filename": filename,
        "path_parts": folder_parts,
    }

    skip_folders = {"docs", "documentation", "wiki", "src", "lib", "pkg"}
    for part in folder_parts:
        if part.lower() not in skip_folders:
            metadata["repo"] = part.lower().replace("_", "-")
            break

    filename_lower = filename.lower()
    for hint, doc_type in _DOC_TYPE_HINTS.items():
        if hint in filename_lower:
            metadata["doc_type"] = doc_type
            break

    for part in folder_parts:
        part_lower = part.lower()
        if part_lower in ("docs", "documentation", "wiki"):
            metadata["category"] = "documentation"
            break
        if part_lower in ("examples", "samples"):
            metadata["category"] = "examples"
            break

    return metadata


def build_header_path(metadata: dict[str, Any]) -> str:
    """Строит breadcrumb-путь из иерархии заголовков.

    Формирует читаемый путь навигации по документу
    на основе вложенных заголовков H1 > H2 > H3.

    Args:
        metadata: Словарь с ключами header_1, header_2, header_3.

    Returns:
        Строка вида "Header1 > Header2 > Header3" или fallback на имя файла.

    """
    headers = [
        metadata.get(key) for key in ("header_1", "header_2", "header_3") if metadata.get(key)
    ]
    if headers:
        return " > ".join(headers)
    return f"File: {metadata.get('source_file', 'unknown')}"


def process_markdown_ast(text: str) -> tuple[str, list[ExtractedBlock]]:
    """Парсит Markdown через AST для извлечения структурных блоков.

    Использует Marko GFM (GitHub Flavored Markdown) для разбора.
    Извлекает блоки кода и таблицы, заменяя их на плейсхолдеры
    для последующей обработки.

    Args:
        text: Текст markdown-секции для парсинга.

    Returns:
        Кортеж: (текст с плейсхолдерами, список ExtractedBlock объектов).

    """
    parsed = _marko_parser.parse(text)

    blocks: list[ExtractedBlock] = []
    new_content_parts = []

    for child in parsed.children:
        if isinstance(child, FencedCode):
            lang = child.lang or "text"
            code_content = child.children[0].children if child.children else ""
            if isinstance(code_content, list):
                code_content = "".join(code_content)

            snippet = code_content.split("\n")[0][:50]
            blocks.append(ExtractedBlock("code", code_content, lang, snippet))

            new_content_parts.append(f"\n>>>CODE_BLOCK_{len(blocks) - 1}_{lang}<<<\n")

        elif isinstance(child, Table):
            table_md = _marko_parser.render(child)
            blocks.append(ExtractedBlock("table", table_md, snippet="Table data..."))
            new_content_parts.append(f"\n>>>TABLE_BLOCK_{len(blocks) - 1}<<<\n")

        else:
            new_content_parts.append(_marko_parser.render(child))

    return "".join(new_content_parts), blocks


def build_vector_text(service: str, header_path: str, chunk_text: str) -> str:
    """Создаёт обогащённый текст для векторного эмбеддинга.

    Объединяет контекстную информацию (сервис, путь заголовков)
    с текстом чанка для улучшения качества семантического поиска.

    Args:
        service: Название сервиса/bounded context.
        header_path: Breadcrumb-путь по заголовкам документа.
        chunk_text: Основной текст чанка.

    Returns:
        Форматированная строка: "service > header_path : chunk_text".

    """
    return f"{service} > {header_path} : {chunk_text}"
