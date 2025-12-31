"""Инфраструктурный слой: работа с хранилищами данных."""

from src.infrastructure.persistence.file_registry import (
    OPENSEARCH_FILES_INDEX,
    calculate_file_hash,
    detect_file_changes,
    ensure_opensearch_files_index,
    load_file_hashes,
    update_file_hashes,
)
from src.infrastructure.persistence.indexer import (
    delete_by_source_file,
    ensure_milvus_collection,
    ensure_opensearch_children_index,
    ensure_opensearch_parent_index,
    index_children_to_milvus,
    index_children_to_opensearch,
    index_data,
    index_parents_to_opensearch,
    init_opensearch,
)
from src.infrastructure.persistence.splitter import (
    process_files,
    process_specific_files,
)

__all__ = [

    "OPENSEARCH_FILES_INDEX",
    "calculate_file_hash",
    "detect_file_changes",
    "ensure_opensearch_files_index",
    "load_file_hashes",
    "update_file_hashes",

    "delete_by_source_file",
    "ensure_milvus_collection",
    "ensure_opensearch_children_index",
    "ensure_opensearch_parent_index",
    "index_children_to_milvus",
    "index_children_to_opensearch",
    "index_data",
    "index_parents_to_opensearch",
    "init_opensearch",

    "process_files",
    "process_specific_files",
]
