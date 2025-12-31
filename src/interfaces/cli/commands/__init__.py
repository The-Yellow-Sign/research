"""CLI команды.

Содержит команды для запуска из терминала:
- ingest.py — команда для индексации документов
"""

from src.interfaces.cli.commands.ingest import main as ingest_main, run_ingest

__all__ = [
    "run_ingest",
    "ingest_main",
]
