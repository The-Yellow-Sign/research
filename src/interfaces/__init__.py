"""Интерфейсный слой приложения.

Содержит:
- api/ — FastAPI HTTP API
- cli/ — терминальный интерфейс (запуск: python -m src.interfaces.cli)
"""

from src.interfaces.api import app

__all__ = ["app"]
