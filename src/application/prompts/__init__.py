"""Управление LLM-промптами.

Содержит:
- manager.py — PromptManager (загрузка и форматирование промптов)
- templates/ — YAML-файлы с шаблонами промптов
"""

from src.application.prompts.manager import (
    BATCH_SUMMARY_PROMPT,
    JSON_FIX_PROMPT,
    RERANKER_PROMPT_BATCH,
    RERANKER_PROMPT_SINGLE,
    SUMMARY_PROMPT,
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
    "RERANKER_PROMPT_SINGLE",
    "RERANKER_PROMPT_BATCH",
    "JSON_FIX_PROMPT",
    "SUMMARY_PROMPT",
    "BATCH_SUMMARY_PROMPT",
]
