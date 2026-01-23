"""Модуль индексации данных в OpenSearch и Milvus.

Отвечает за:
- Создание и управление индексами/коллекциями
- Bulk-индексацию parents и children
- Удаление документов по source_file
"""

import logging
from typing import Any

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)
from sentence_transformers import SentenceTransformer

from src.config import settings
from src.infrastructure.persistence.file_registry import ensure_opensearch_files_index

logger = logging.getLogger(__name__)


def ensure_opensearch_parent_index(client: OpenSearch) -> bool:
    """Создаёт OpenSearch Parent-индекс."""
    if client.indices.exists(index=settings.opensearch_parent_index):
        return False

    index_body = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "date_detection": False,
            "properties": {
                "id": {"type": "keyword"},
                "full_text": {"type": "text", "index": False},
                "source_file": {"type": "keyword"},
                "service": {"type": "keyword"},
                "header_path": {"type": "keyword"},
                "mentions": {
                    "type": "object",
                    "dynamic": True,
                },
            },
        },
    }

    client.indices.create(index=settings.opensearch_parent_index, body=index_body)
    logger.info("Создан parent-индекс: %s", settings.opensearch_parent_index)
    return True


def ensure_opensearch_children_index(client: OpenSearch) -> bool:
    """Создаёт OpenSearch Children-индекс."""
    if client.indices.exists(index=settings.opensearch_index):
        return False

    index_body = {
        "settings": {
            "analysis": {
                "analyzer": {
                    "ngram_analyzer": {
                        "tokenizer": "ngram_tokenizer",
                        "filter": ["lowercase"],
                    }
                },
                "tokenizer": {
                    "ngram_tokenizer": {
                        "type": "ngram",
                        "min_gram": 3,
                        "max_gram": 4,
                        "token_chars": ["letter", "digit"],
                    }
                },
            }
        },
        "mappings": {
            "properties": {
                "content": {
                    "type": "text",
                    "fields": {"ngram": {"type": "text", "analyzer": "ngram_analyzer"}},
                },
                "raw_content": {"type": "text", "index": True, "analyzer": "standard"},
                "parent_id": {"type": "keyword"},
                "chunk_type": {"type": "keyword"},
                "source_file": {"type": "keyword"},
                "service": {"type": "keyword"},
                "header_path": {"type": "text"},
            }
        },
    }

    client.indices.create(index=settings.opensearch_index, body=index_body)
    logger.info("Создан children-индекс: %s", settings.opensearch_index)
    return True


def ensure_milvus_collection(vector_dim: int) -> Collection:
    """Создаёт коллекцию Milvus."""
    logger.info("Подключение к Milvus: %s:%s", settings.milvus_host, settings.milvus_port)
    connections.connect("default", host=settings.milvus_host, port=settings.milvus_port)

    if utility.has_collection(settings.milvus_collection):
        collection = Collection(settings.milvus_collection)
        collection.load()
        return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=vector_dim),
        FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=60000),
        FieldSchema(name="raw_content", dtype=DataType.VARCHAR, max_length=60000),
        FieldSchema(name="parent_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="chunk_type", dtype=DataType.VARCHAR, max_length=32),
        FieldSchema(name="source_file", dtype=DataType.VARCHAR, max_length=512),
        FieldSchema(name="header_path", dtype=DataType.VARCHAR, max_length=2048),
        FieldSchema(name="service", dtype=DataType.VARCHAR, max_length=128),
    ]

    schema = CollectionSchema(fields, description="DevOps Knowledge Base - Children")
    collection = Collection(settings.milvus_collection, schema)

    index_params = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 128},
    }
    collection.create_index(field_name="vector", index_params=index_params)
    collection.load()

    logger.info("Создана коллекция: %s", settings.milvus_collection)
    return collection


def init_opensearch() -> OpenSearch:
    """Инициализирует OpenSearch-клиент и создаёт ВСЕ индексы."""
    logger.info(
        "Подключение к OpenSearch: %s:%s", settings.opensearch_host, settings.opensearch_port
    )

    client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        http_compress=True,
        use_ssl=False,
        connection_pool_kwargs={"maxsize": 50},
    )

    ensure_opensearch_parent_index(client)
    ensure_opensearch_children_index(client)
    ensure_opensearch_files_index(client)

    return client


def delete_by_source_file(
    os_client: OpenSearch,
    milvus_collection: Collection,
    source_files: list[str],
) -> None:
    """Удаляет все документы для указанных файлов (по полному относительному пути)."""
    if not source_files:
        return

    logger.info("Удаление данных для %d файлов...", len(source_files))

    for source_file in source_files:
        target_file = source_file

        try:
            os_client.delete_by_query(
                index=settings.opensearch_parent_index,
                body={"query": {"term": {"source_file": target_file}}},
                ignore=[404],
            )
        except Exception as e:
            logger.warning("Ошибка удаления parents для %s: %s", target_file, e)

        try:
            os_client.delete_by_query(
                index=settings.opensearch_index,
                body={"query": {"term": {"source_file": target_file}}},
                ignore=[404],
            )
        except Exception as e:
            logger.warning("Ошибка удаления children из OpenSearch для %s: %s", target_file, e)

        try:
            safe_file = target_file.replace('"', '\\"')
            expr = f'source_file == "{safe_file}"'
            milvus_collection.delete(expr)
        except Exception as e:
            logger.warning("Ошибка удаления из Milvus для %s: %s", target_file, e)

    logger.info("Удаление завершено для %d файлов", len(source_files))


def index_parents_to_opensearch(
    client: OpenSearch,
    parents: list[dict[str, Any]],
) -> None:
    """Bulk-индексация parent-документов."""
    if not parents:
        return

    actions = [
        {
            "_index": settings.opensearch_parent_index,
            "_id": parent["id"],
            "_source": {
                "id": parent["id"],
                "full_text": parent["full_text"],
                "source_file": parent["metadata"].get("source_file"),
                "service": parent["metadata"].get("service"),
                "header_path": parent["metadata"].get("header_path"),
                "mentions": parent["metadata"].get("mentions", {}),
            },
        }
        for parent in parents
    ]

    bulk(client, actions)
    client.indices.refresh(index=settings.opensearch_parent_index)
    logger.info("Проиндексировано %d parents в OpenSearch", len(parents))


def index_children_to_opensearch(
    client: OpenSearch,
    children: list[dict[str, Any]],
) -> None:
    """Bulk-индексация children-документов."""
    if not children:
        return

    actions = [
        {
            "_index": settings.opensearch_index,
            "_source": {
                "content": child["text"],
                "raw_content": child["raw_content"],
                "parent_id": child["metadata"].get("parent_id"),
                "chunk_type": child.get("chunk_type", "text"),
                "source_file": child["metadata"].get("source_file"),
                "service": child["metadata"].get("service"),
                "header_path": child["metadata"].get("header_path"),
            },
        }
        for child in children
    ]

    bulk(client, actions)
    client.indices.refresh(index=settings.opensearch_index)
    logger.info("Проиндексировано %d children в OpenSearch", len(children))


def index_children_to_milvus(
    collection: Collection,
    model: SentenceTransformer,
    children: list[dict[str, Any]],
) -> None:
    """Batch-индексация children в Milvus.

    Добавляет логирование статистики токенов для мониторинга
    лимита FRIDA (512 токенов).
    """
    if not children:
        return

    total_batches = (len(children) + settings.milvus_batch_size - 1) // settings.milvus_batch_size
    all_token_lengths: list[int] = []
    overflow_count = 0
    frida_max_tokens = settings.embedding_model_max_tokens

    for batch_idx, start in enumerate(range(0, len(children), settings.milvus_batch_size)):
        batch = children[start : start + settings.milvus_batch_size]

        vector_texts = [child["vector_text"] for child in batch]
        texts = [child["text"] for child in batch]
        raw_contents = [child["raw_content"] for child in batch]
        metas = [child["metadata"] for child in batch]
        chunk_types = [child.get("chunk_type", "text") for child in batch]

        prefixed_texts = [f"{settings.doc_prefix}{vt}" for vt in vector_texts]

        tokenizer = model.tokenizer
        for i, text in enumerate(prefixed_texts):
            tokens = len(tokenizer.encode(text))
            all_token_lengths.append(tokens)
            if tokens > frida_max_tokens:
                overflow_count += 1
                logger.warning(
                    "Token overflow: %d > %d в файле %s",
                    tokens,
                    frida_max_tokens,
                    metas[i].get("source_file", "unknown"),
                )

        vectors = model.encode(prefixed_texts, show_progress_bar=False)

        collection.insert(
            [
                vectors.tolist(),
                texts,
                raw_contents,
                [meta.get("parent_id", "") for meta in metas],
                chunk_types,
                [meta.get("source_file", "") for meta in metas],
                [meta.get("header_path", "") for meta in metas],
                [meta.get("service", "general") for meta in metas],
            ]
        )

        logger.info("Проиндексирован batch %d/%d в Milvus", batch_idx + 1, total_batches)

    collection.flush()

    if all_token_lengths:
        avg_tokens = sum(all_token_lengths) / len(all_token_lengths)
        logger.info(
            "Статистика токенов: min=%d, max=%d, avg=%.1f, overflow=%d/%d",
            min(all_token_lengths),
            max(all_token_lengths),
            avg_tokens,
            overflow_count,
            len(all_token_lengths),
        )

    logger.info("Проиндексировано %d children в Milvus", len(children))


def index_data(
    os_client: OpenSearch,
    milvus_collection: Collection,
    model: SentenceTransformer,
    parents: list[dict[str, Any]],
    children: list[dict[str, Any]],
) -> None:
    """Индексирует parents и children во все базы данных."""
    if not parents and not children:
        logger.warning("Нет документов для индексации")
        return

    logger.info("Начало индексации: %d parents, %d children", len(parents), len(children))

    index_parents_to_opensearch(os_client, parents)
    index_children_to_opensearch(os_client, children)
    index_children_to_milvus(milvus_collection, model, children)
