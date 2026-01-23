"""Централизованная конфигурация логирования.

Единая точка настройки логов для всего приложения.
Вызывается в entry-points: api.py, bot.py, ingest.py
"""

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Настраивает логирование для всего приложения.

    Args:
        level: Уровень логирования (по умолчанию INFO).

    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
