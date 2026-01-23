"""Data Transfer Objects.

Содержит Pydantic-модели для передачи данных между слоями:
- requests.py — входящие запросы (ChatRequest)
- responses.py — исходящие ответы (ChatResponse)
"""

from src.application.dto.requests import ChatRequest
from src.application.dto.responses import ChatResponse

__all__ = [
    "ChatRequest",
    "ChatResponse",
]
