"""Port для векторного хранилища.

Определяет абстрактный интерфейс для работы с векторными базами данных.
Реализации (Adapters) находятся в infrastructure/search/.
"""

from typing import Any, Protocol


class VectorStorePort(Protocol):
    """Абстракция для векторного хранилища (Milvus, Pinecone, etc.).

    Определяет контракт для семантического поиска по эмбеддингам.
    """

    def search(
        self,
        query: str,
        top_k: int = 25,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Выполняет семантический поиск по векторам.

        Args:
            query: Текстовый запрос (будет преобразован в эмбеддинг).
            top_k: Количество результатов.
            filters: Опциональные фильтры (например, {"service": "postgres"}).

        Returns:
            Список найденных документов с метаданными и scores.

        """
        ...

    def get_embedding(self, text: str) -> list[float]:
        """Получает эмбеддинг для текста.

        Args:
            text: Входной текст.

        Returns:
            Вектор эмбеддинга.

        """
        ...
