"""Application Layer — слой приложения.

Содержит:
- use_cases/ — сценарии использования (оркестрация бизнес-логики)
- dto/ — Data Transfer Objects (контракты между слоями)
- prompts/ — управление LLM-промптами
- services/ — фасады для внешних интерфейсов

Этот слой зависит от domain/, но НЕ зависит от infrastructure/.
"""

from src.application.dto import ChatRequest, ChatResponse
from src.application.prompts import (
    SYSTEM_ANALYZER,
    SYSTEM_CLARIFY,
    SYSTEM_MAIN,
    SYSTEM_QUERY_EXPANSION,
    PromptManager,
    format_analysis_prompt,
    format_query_rewrite_prompt,
)
from src.application.services import RAGService
from src.application.use_cases import DocumentAnalyzer, QueryExpander, QueryProcessor

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "QueryProcessor",
    "QueryExpander",
    "DocumentAnalyzer",
    "RAGService",
    "PromptManager",
    "format_analysis_prompt",
    "format_query_rewrite_prompt",
    "SYSTEM_MAIN",
    "SYSTEM_QUERY_EXPANSION",
    "SYSTEM_ANALYZER",
    "SYSTEM_CLARIFY",
]
