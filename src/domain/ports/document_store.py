"""Port для документного хранилища.

Определяет абстрактный интерфейс для работы с документными базами данных.
Реализации (Adapters) находятся в infrastructure/search/.
"""

from typing import Any, Protocol


class DocumentStorePort(Protocol):
    """Абстракция для документного хранилища (OpenSearch, Elasticsearch, etc.).

    Определяет контракт для полнотекстового поиска и хранения документов.
    """

    def search_fulltext(
        self,
        query: str,
        top_k: int = 25,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Выполняет полнотекстовый поиск.

        Args:
            query: Текстовый запрос.
            top_k: Количество результатов.
            filters: Опциональные фильтры.

        Returns:
            Список найденных документов с метаданными и scores.

        """
        ...

    def fetch_by_ids(self, ids: list[str]) -> list[dict[str, Any]]:
        """Получает документы по списку ID.

        Args:
            ids: Список идентификаторов документов.

        Returns:
            Список документов (full_text, metadata).

        """
        ...

    def index_documents(self, documents: list[dict[str, Any]]) -> int:
        """Индексирует документы в хранилище.

        Args:
            documents: Список документов для индексации.

        Returns:
            Количество успешно проиндексированных документов.

        """
        ...

    def delete_by_source(self, source_files: list[str]) -> int:
        """Удаляет документы по source_file.

        Args:
            source_files: Список путей к исходным файлам.

        Returns:
            Количество удалённых документов.

        """
        ...
