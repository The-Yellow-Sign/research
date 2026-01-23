"""Точка входа для запуска RAG-чатбота.

Запускает терминальный UI для интерактивного взаимодействия с RAG-системой.
"""

import multiprocessing
import os

if hasattr(multiprocessing, "set_start_method"):
    try:
        multiprocessing.set_start_method("spawn", force=True)
    except RuntimeError:
        pass


os.environ["TOKENIZERS_PARALLELISM"] = "false"

from src.interfaces.cli import main

if __name__ == "__main__":
    main()
