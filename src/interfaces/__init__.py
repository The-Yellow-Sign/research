"""Интерфейсный слой приложения.

Содержит:
- api/ — FastAPI HTTP API
- cli/ — терминальный интерфейс
"""

from src.interfaces.api import app
from src.interfaces.cli import TerminalUI, main

__all__ = ["app", "TerminalUI", "main"]
