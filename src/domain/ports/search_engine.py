"""Port для поискового движка.

Определяет интерфейс для гибридного поиска (Milvus + OpenSearch).
Реализации находятся в infrastructure/search/.
"""

from typing import Any, Protocol


class SearchEnginePort(Protocol):
    """Абстракция для поискового движка.

    Объединяет семантический (Milvus) и лексический (OpenSearch) поиск.
    """

    async def retrieve_candidates(
        self,
        query: str,
        filters: dict[str, Any] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Получает кандидатов через гибридный поиск.

        Args:
            query: Текстовый запрос.
            filters: Опциональные фильтры.

        Returns:
            Словарь {parent_id: doc_data} с RRF-скорами.

        """
        ...

    def rerank_candidates(
        self,
        query: str,
        candidates: dict[str, dict[str, Any]],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Реранжирует кандидатов через Cross-Encoder.

        Args:
            query: Запрос для оценки релевантности.
            candidates: Кандидаты из retrieve_candidates.
            top_k: Количество лучших результатов.

        Returns:
            Отсортированный список документов.

        """
        ...
