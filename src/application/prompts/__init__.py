"""Управление LLM-промптами.

Содержит:
- manager.py — PromptManager (загрузка и форматирование промптов)
- templates/ — YAML-файлы с шаблонами промптов
"""

from src.application.prompts.manager import (
    SYSTEM_ANALYZER,
    SYSTEM_CLARIFY,
    SYSTEM_MAIN,
    SYSTEM_QUERY_EXPANSION,
    PromptManager,
    format_analysis_prompt,
    format_query_rewrite_prompt,
)

__all__ = [
    "PromptManager",
    "format_analysis_prompt",
    "format_query_rewrite_prompt",
    "SYSTEM_MAIN",
    "SYSTEM_QUERY_EXPANSION",
    "SYSTEM_ANALYZER",
    "SYSTEM_CLARIFY",
]
