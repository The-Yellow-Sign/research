"""Менеджер наблюдений с контролем токенов."""

import logging
from dataclasses import dataclass

import tiktoken

logger = logging.getLogger(__name__)


@dataclass
class Observation:
    """Структура одного наблюдения."""

    content: str
    priority: int
    tokens: int


class ObservationManager:
    """Управление контекстом наблюдений с приоритетами."""

    def __init__(self, max_tokens: int = 8000):
        self.max_tokens = max_tokens
        self.observations: list[Observation] = []
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self.tokenizer = None
            logger.warning("Could not initialize tiktoken, token counting will be approximate")

    def add(self, content: str, priority: int = 1) -> None:
        """Добавляет observation с приоритетом (1-low, 3-high)."""
        tokens = self._count_tokens(content)
        self.observations.append(Observation(content=content, priority=priority, tokens=tokens))
        self._trim_if_needed()

    def _count_tokens(self, text: str) -> int:
        """Считает количество токенов."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Для кириллицы более точное приближение (~3 байта на токен)
        return len(text.encode("utf-8")) // 3

    def _trim_if_needed(self) -> None:
        """Удаляет низкоприоритетные observations при переполнении."""
        total = sum(o.tokens for o in self.observations)

        while total > self.max_tokens and self.observations:
            low_priority_idx = -1
            for i, o in enumerate(self.observations):
                if o.priority < 3:
                    low_priority_idx = i
                    break

            if low_priority_idx != -1:
                item = self.observations.pop(low_priority_idx)
                total -= item.tokens
                logger.info("Trimmed low-priority observation (%d tokens)", item.tokens)
            else:
                item = self.observations.pop(0)
                total -= item.tokens
                logger.info("Trimmed oldest high-priority observation (%d tokens)", item.tokens)

    def get_context(self) -> str:
        """Возвращает объединённый контекст."""
        return "\n".join(o.content for o in self.observations)

    def as_list(self) -> list[str]:
        """Возвращает список строк (для совместимости)."""
        return [o.content for o in self.observations]

    def count_pattern(self, pattern: str) -> int:
        """Считает вхождения паттерна в наблюдениях."""
        count = 0
        p_lower = pattern.lower()
        for obs in self.observations:
            if p_lower in obs.content.lower():
                count += 1
        return count

    def clear(self) -> None:
        """Очищает все наблюдения."""
        self.observations.clear()
