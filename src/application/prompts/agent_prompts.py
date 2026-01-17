"""Загрузчик агентских промптов из YAML.

Singleton-паттерн для эффективного кэширования.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

AGENT_PROMPTS_PATH = Path(__file__).parent / "templates" / "agent_prompts.yaml"


class AgentPromptManager:
    """Менеджер агентских промптов.

    Загружает промпты из agent_prompts.yaml при первом обращении.
    Использует Singleton-паттерн для кэширования.

    """

    _instance = None
    _prompts: dict[str, Any] = {}

    def __new__(cls):
        """Создаёт или возвращает единственный экземпляр."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """Загружает промпты из YAML."""
        if not AGENT_PROMPTS_PATH.exists():
            raise FileNotFoundError(f"Agent prompts not found: {AGENT_PROMPTS_PATH}")

        with open(AGENT_PROMPTS_PATH, encoding="utf-8") as f:
            self._prompts = yaml.safe_load(f)
        logger.info("Agent prompts loaded from YAML")

    def get(self, key: str, default: str = "") -> str:
        """Возвращает промпт по ключу."""
        return self._prompts.get(key, default)

    def get_nested(self, *keys: str, default: str = "") -> str:
        """Возвращает вложенный промпт."""
        result = self._prompts
        for key in keys:
            if isinstance(result, dict):
                result = result.get(key, {})
            else:
                return default
        return result if isinstance(result, str) else default

    def format(self, key: str, **kwargs: Any) -> str:
        """Форматирует промпт с подстановкой переменных."""
        template = self.get(key)
        if not template:
            raise ValueError(f"Prompt '{key}' not found")
        return template.format(**kwargs)

    @property
    def system_prompt(self) -> str:
        """Системный промпт агента."""
        return self.get("agent_system", "")

    @property
    def think_template(self) -> str:
        """Шаблон для think-промпта."""
        return self.get("agent_think", "")

    def get_urgency_hint(self, step: int, threshold: int = 3) -> str:
        """Возвращает hint в зависимости от шага."""
        hints = self._prompts.get("urgency_hints", {})
        if step >= threshold:
            return hints.get("late", "")
        return hints.get("early", "")

    def get_fallback_message(self, key: str) -> str:
        """Возвращает fallback-сообщение по ключу."""
        fallbacks = self._prompts.get("fallback_messages", {})
        return fallbacks.get(key, "")


_agent_prompts = AgentPromptManager()

AGENT_SYSTEM_PROMPT = _agent_prompts.system_prompt
AGENT_THINK_TEMPLATE = _agent_prompts.think_template


def get_agent_prompts() -> AgentPromptManager:
    """Возвращает экземпляр AgentPromptManager."""
    return _agent_prompts
