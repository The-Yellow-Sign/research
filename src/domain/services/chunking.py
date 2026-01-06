"""Доменный сервис чанкинга.

Содержит чистую бизнес-логику разбиения документов:
- parse_frontmatter — извлечение YAML frontmatter
- infer_service_from_path — определение сервиса по пути
- build_header_path — построение breadcrumb-пути
- process_markdown_ast — AST-парсинг markdown
- build_vector_text — создание обогащённого текста для эмбеддинга

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


KNOWN_SERVICES: set[str] = {
    "nginx",
    "apache",
    "mysql",
    "postgres",
    "postgresql",
    "redis",
    "mongodb",
    "mongo",
    "k8s",
    "kubernetes",
    "docker",
    "ansible",
    "jenkins",
    "gitlab",
    "python",
    "java",
    "go",
    "golang",
    "nodejs",
    "node",
    "elasticsearch",
    "rabbitmq",
    "prometheus",
    "grafana",
    "ssh",
    "git",
    "linux",
    "terraform",
    "aws",
    "azure",
    "gcp",
}

SERVICE_ALIASES: dict[str, str] = {
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "postgres": "postgres",
    "postgresql": "postgres",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "node": "nodejs",
    "nodejs": "nodejs",
    "golang": "go",
}


_marko_parser = gfm


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Извлекает YAML frontmatter из markdown-содержимого.

    Args:
        text: Полный текст markdown-документа.

    Returns:
        Кортеж (frontmatter_dict, content_without_frontmatter).

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


def infer_service_from_path(filepath: Path) -> str | None:
    """Определяет сервис по названию родительских папок.

    Args:
        filepath: Путь к файлу.

    Returns:
        Название сервиса или None, если не определено.

    """
    for part in reversed(filepath.parent.parts):
        part_lower = part.lower()
        if part_lower in KNOWN_SERVICES:
            return SERVICE_ALIASES.get(part_lower, part_lower)
    return None


def build_header_path(metadata: dict[str, Any]) -> str:
    """Строит breadcrumb-путь из метаданных заголовков.

    Args:
        metadata: Метаданные с ключами header_1, header_2, header_3.

    Returns:
        Строка вида "Header1 > Header2 > Header3" или путь к файлу.

    """
    headers = [
        metadata.get(key) for key in ("header_1", "header_2", "header_3") if metadata.get(key)
    ]
    if headers:
        return " > ".join(headers)
    return f"File: {metadata.get('source_file', 'unknown')}"


def process_markdown_ast(text: str) -> tuple[str, list[ExtractedBlock]]:
    """Парсит Markdown через AST (Marko) для безопасного извлечения блоков.

    Извлекает блоки кода и таблицы, заменяя их на плейсхолдеры.

    Args:
        text: Текст markdown-секции.

    Returns:
        Кортеж (текст_с_плейсхолдерами, список_блоков).

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
    """Строит обогащённый текст для векторного эмбеддинга.

    Args:
        service: Название сервиса.
        header_path: Breadcrumb-путь заголовков.
        chunk_text: Текст чанка.

    Returns:
        Обогащённый текст формата "service > header_path : chunk_text".

    """
    return f"{service} > {header_path} : {chunk_text}"
