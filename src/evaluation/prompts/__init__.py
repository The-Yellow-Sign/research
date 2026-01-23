"""Загрузчик промптов для RAGAS evaluation.

Загружает русскоязычные промпты из YAML-файла.
"""

import logging
from functools import lru_cache
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

PROMPTS_FILE = Path(__file__).parent / "ragas_prompts.yaml"


@lru_cache(maxsize=1)
def load_ragas_prompts() -> dict[str, str]:
    """Загружает промпты для RAGAS из YAML-файла.

    Returns:
        Словарь с промптами {prompt_name: prompt_text}.

    """
    if not PROMPTS_FILE.exists():
        logger.warning("RAGAS prompts file not found: %s", PROMPTS_FILE)
        return {}

    with PROMPTS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    prompts = data.get("prompts", {})
    json_suffix = data.get("json_suffix", "")

    prompts_with_suffix = [
        "faithfulness_prompt",
        "context_recall_prompt",
        "context_precision_prompt",
    ]

    for name in prompts_with_suffix:
        if name in prompts:
            prompts[name] = prompts[name].rstrip() + json_suffix

    logger.info("Loaded %d RAGAS prompts from %s", len(prompts), PROMPTS_FILE.name)
    return prompts


def get_ragas_prompt(name: str) -> str | None:
    """Получает промпт по имени.

    Args:
        name: Имя промпта (faithfulness_prompt, answer_relevancy_prompt, etc.)

    Returns:
        Текст промпта или None, если не найден.

    """
    prompts = load_ragas_prompts()
    return prompts.get(name)
