"""Инфраструктурный слой приложения.

Содержит:
- llm/ — клиенты для взаимодействия с LLM
- persistence/ — работа с хранилищами данных (индексация, файловый реестр, splitter)
- search/ — поисковые клиенты (Milvus, OpenSearch)

ВАЖНО: LLMClient не экспортируется здесь для избежания циклического импорта.
Используйте: from src.infrastructure.llm.client import LLMClient
"""

from src.infrastructure.persistence import (
    OPENSEARCH_FILES_INDEX,
    delete_by_source_file,
    detect_file_changes,
    ensure_milvus_collection,
    index_data,
    init_opensearch,
    process_files,
    process_specific_files,
    update_file_hashes,
)
from src.infrastructure.search import MilvusClient, OpenSearchClient, SearchEngine

__all__ = [

    "OPENSEARCH_FILES_INDEX",
    "delete_by_source_file",
    "detect_file_changes",
    "ensure_milvus_collection",
    "index_data",
    "init_opensearch",
    "process_files",
    "process_specific_files",
    "update_file_hashes",

    "SearchEngine",
    "MilvusClient",
    "OpenSearchClient",
]
