"""Пакет конфигурации RAG-приложения.

Содержит:
- settings: Pydantic Settings для управления конфигурацией
- logging_config: Централизованное логирование
- telemetry: OpenTelemetry трейсинг

Для обратной совместимости экспортируются константы из settings.
"""

from src.config.settings import settings

PROJECT_ROOT = settings.project_root
SOURCE_DIR = settings.source_dir


MILVUS_HOST = settings.milvus_host
MILVUS_PORT = settings.milvus_port
MILVUS_COLLECTION = settings.milvus_collection
MILVUS_BATCH_SIZE = settings.milvus_batch_size


OPENSEARCH_HOST = settings.opensearch_host
OPENSEARCH_PORT = settings.opensearch_port
OPENSEARCH_INDEX = settings.opensearch_index
OPENSEARCH_PARENT_INDEX = settings.opensearch_parent_index


EMBEDDING_MODEL_NAME = settings.embedding_model_name
DOC_PREFIX = settings.doc_prefix
QUERY_PREFIX = settings.query_prefix
RERANKER_MODEL_NAME = settings.reranker_model_name
RERANK_MAX_CHARS = settings.rerank_max_chars


LLM_BASE_URL = settings.llm_base_url
LLM_MODEL = settings.llm_model
LLM_API_KEY = settings.llm_api_key


CHUNK_SIZE = settings.chunk_size
CHUNK_OVERLAP = settings.chunk_overlap
MIN_CHUNK_CHARS = settings.min_chunk_chars
CODE_BLOCK_PATTERN = settings.code_block_pattern


TOP_K_MILVUS = settings.top_k_milvus
TOP_K_OPENSEARCH = settings.top_k_opensearch
FINAL_TOP_K = settings.final_top_k
RRF_K = settings.rrf_k


MIN_RELEVANCE_SCORE = settings.min_relevance_score
LLM_CONCURRENCY_LIMIT = settings.llm_concurrency_limit


LLM_TIMEOUT = settings.llm_timeout
MAX_CONTEXT_CHARS = settings.max_context_chars

__all__ = [
    "settings",

    "PROJECT_ROOT",
    "SOURCE_DIR",
    "MILVUS_HOST",
    "MILVUS_PORT",
    "MILVUS_COLLECTION",
    "MILVUS_BATCH_SIZE",
    "OPENSEARCH_HOST",
    "OPENSEARCH_PORT",
    "OPENSEARCH_INDEX",
    "OPENSEARCH_PARENT_INDEX",
    "EMBEDDING_MODEL_NAME",
    "DOC_PREFIX",
    "QUERY_PREFIX",
    "RERANKER_MODEL_NAME",
    "RERANK_MAX_CHARS",
    "LLM_BASE_URL",
    "LLM_MODEL",
    "LLM_API_KEY",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "MIN_CHUNK_CHARS",
    "CODE_BLOCK_PATTERN",
    "TOP_K_MILVUS",
    "TOP_K_OPENSEARCH",
    "FINAL_TOP_K",
    "MIN_RELEVANCE_SCORE",
    "LLM_CONCURRENCY_LIMIT",
]
