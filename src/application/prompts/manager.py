"""Менеджер LLM-промптов.

Загружает шаблоны из YAML и предоставляет функции форматирования.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


PROMPTS_PATH = Path(__file__).parent / "templates" / "prompts.yaml"


class PromptManager:
    """Singleton для загрузки и хранения промптов.

    Загружает промпты из YAML-файла при первом обращении.
    Предоставляет методы для получения и форматирования промптов.

    """

    _instance = None
    _prompts: dict[str, str] = {}

    def __new__(cls):
        """Создаёт или возвращает единственный экземпляр PromptManager."""
        if cls._instance is None:
            cls._instance = super(PromptManager, cls).__new__(cls)
            cls._instance._load_prompts()
        return cls._instance

    def _load_prompts(self) -> None:
        """Загружает промпты из YAML-файла.

        Raises:
            FileNotFoundError: Если файл prompts.yaml не найден.
            yaml.YAMLError: Если файл содержит невалидный YAML.

        """
        if not PROMPTS_PATH.exists():
            raise FileNotFoundError(f"Файл промптов не найден: {PROMPTS_PATH}")

        try:
            with open(PROMPTS_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self._prompts = data.get("prompts", {})
            logger.info("Промпты успешно загружены из YAML")
        except Exception as e:
            logger.error("Ошибка загрузки промптов: %s", e)
            raise

    def get(self, key: str) -> str:
        """Возвращает сырой шаблон промпта по ключу.

        Args:
            key: Ключ промпта.

        Returns:
            Шаблон промпта или пустая строка.

        """
        return self._prompts.get(key, "")

    def format(self, key: str, **kwargs: Any) -> str:
        """Возвращает отформатированный промпт.

        Args:
            key: Ключ промпта.
            **kwargs: Переменные для подстановки.

        Returns:
            Отформатированный промпт.

        Raises:
            KeyError: Если в шаблоне есть переменная, которая не передана в kwargs.
            ValueError: Если шаблон пуст или не найден.

        """
        template = self.get(key)
        if not template:
            logger.error("CRITICAL: Промпт '%s' не найден или пуст", key)
            raise ValueError(f"Промпт '{key}' отсутствует")

        return template.format(**kwargs)


def format_analysis_prompt(query: str, content: str) -> str:
    """Форматирует промпт для анализа релевантности документа.

    Args:
        query: Запрос пользователя.
        content: Содержимое документа.

    Returns:
        Отформатированный промпт.

    """
    manager = PromptManager()
    return manager.format("user_analyze", query=query, content=content)


def format_query_rewrite_prompt(history_text: str, query: str) -> str:
    """Форматирует промпт для переписывания запроса с учётом истории.

    Args:
        history_text: История диалога в текстовом формате.
        query: Текущий запрос пользователя.

    Returns:
        Отформатированный промпт.

    """
    manager = PromptManager()
    return manager.format("user_rewrite", history=history_text, query=query)


_manager = PromptManager()

SYSTEM_MAIN = _manager.get("system_main")
SYSTEM_QUERY_EXPANSION = _manager.get("system_query_expansion")
SYSTEM_ANALYZER = _manager.get("system_analyzer")
SYSTEM_CLARIFY = _manager.get("system_clarify")

RERANKER_PROMPT_SINGLE = _manager.get("reranker_prompt_single")
RERANKER_PROMPT_BATCH = _manager.get("reranker_prompt_batch")
JSON_FIX_PROMPT = _manager.get("json_fix_prompt")
SUMMARY_PROMPT = _manager.get("summary_prompt")
BATCH_SUMMARY_PROMPT = _manager.get("batch_summary_prompt")
