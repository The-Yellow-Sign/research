"""Port для извлечения метаданных.

Определяет интерфейс для сервисов извлечения метаданных и сущностей из текста.
Реализации (Adapters) находятся в infrastructure/nlp/.
"""

from typing import Protocol


class MetadataExtractorPort(Protocol):
    """Интерфейс для извлечения метаданных и NER."""

    def extract_metadata(
        self,
        text: str,
        labels: list[str] | None = None,
        threshold: float = 0.35,
    ) -> dict[str, list[str]]:
        """Извлекает сущности и метаданные из текста.

        Args:
            text: Исходный текст для анализа.
            labels: Список типов сущностей для поиска.
            threshold: Порог уверенности модели.

        Returns:
            Словарь {тип_сущности: [список_значений]}.

        """
        ...

    async def extract_entities_llm(self, query: str) -> dict[str, list[str]]:
        """Извлекает сущности с помощью LLM (fallback).

        Args:
            query: Текст запроса.

        Returns:
            Словарь {тип_сущности: [список_значений]}.

        """
        ...
