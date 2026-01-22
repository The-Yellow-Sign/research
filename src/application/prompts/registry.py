"""Сервис для управления промптами.

Централизованное хранилище всех промптов (RAG, Agent и др.),
загружаемых из YAML-файлов.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


TEMPLATES_DIR = Path(__file__).parent / "templates"


class PromptRegistry:
    """Реестр для загрузки, хранения и форматирования промптов.

    Singleton для эффективного доступа к промптам из любого места приложения.
    Загружает все YAML файлы из src/application/prompts/templates/.
    """

    _instance = None
    _prompts: dict[str, Any] = {}
    _initialized: bool = False

    def __new__(cls) -> "PromptRegistry":
        """Создает или возвращает единственный экземпляр PromptRegistry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Инициализирует реестр и загружает промпты (только один раз)."""
        if self._initialized:
            return

        self._load_all_prompts()
        self._initialized = True

    def _load_all_prompts(self) -> None:
        """Загружает промпты из всех YAML файлов в директории шаблонов."""
        if not TEMPLATES_DIR.exists():
            logger.error("Директория шаблонов не найдена: %s", TEMPLATES_DIR)
            return

        for yaml_file in TEMPLATES_DIR.glob("*.yaml"):
            try:
                with open(yaml_file, encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                if not data:
                    continue

                if yaml_file.name == "prompts.yaml":
                    self._prompts.update(data.get("prompts", {}))
                elif yaml_file.name == "agent_prompts.yaml":
                    self._prompts.update(data)
                else:
                    self._prompts.update(data)

                logger.debug("Загружен шаблон: %s", yaml_file.name)

            except Exception as e:
                logger.error("Ошибка загрузки %s: %s", yaml_file.name, e)

        logger.info("PromptRegistry инициализирован. Загружено ключей: %d", len(self._prompts))

    def get(self, key: str, default: Any = "") -> Any:
        """Возвращает сырое значение промпта по ключу."""
        return self._prompts.get(key, default)

    def get_nested(self, *keys: str, default: Any = "") -> Any:
        """Возвращает значение вложенного ключа."""
        current = self._prompts
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key, {})
            else:
                return default

        if current == {} and default != "":
            return default
        return current if current is not None else default

    def format(self, key: str, **kwargs: Any) -> str:
        """Возвращает отформатированный строковый промпт."""
        template = self.get(key)
        if not template or not isinstance(template, str):
            logger.warning("Промпт '%s' не найден или не является строкой", key)
            return ""

        try:
            return template.format(**kwargs)
        except KeyError as e:
            logger.error("Ошибка форматирования промпта '%s': пропущен ключ %s", key, e)
            return template
