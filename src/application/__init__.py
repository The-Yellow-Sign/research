"""Application Layer — слой приложения.

Содержит:
- use_cases/ — сценарии использования (оркестрация бизнес-логики)
- dto/ — Data Transfer Objects (контракты между слоями)
- prompts/ — управление LLM-промптами
- services/ — фасады для внешних интерфейсов

Этот слой зависит от domain/, но НЕ зависит от infrastructure/.
"""

from src.application.dto import ChatRequest, ChatResponse
from src.application.services import RAGService
from src.application.use_cases import DocumentAnalyzer, QueryExpander

__all__ = [
    "ChatRequest",
    "ChatResponse",
    "RAGService",
    "QueryExpander",
    "DocumentAnalyzer",
]
