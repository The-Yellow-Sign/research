"""Инфраструктурный слой: поисковые клиенты.

Содержит:
- milvus_client.py — клиент для семантического поиска (Milvus)
- opensearch_client.py — клиент для полнотекстового поиска (OpenSearch)
- engine.py — SearchEngine (фасад для гибридного поиска)
"""

from src.infrastructure.search.engine import SearchEngine
from src.infrastructure.search.milvus_client import MilvusClient
from src.infrastructure.search.opensearch_client import OpenSearchClient

__all__ = [
    "SearchEngine",
    "MilvusClient",
    "OpenSearchClient",
]
