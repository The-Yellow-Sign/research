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

from src.config import (
    DOC_PREFIX,
    MILVUS_BATCH_SIZE,
    MILVUS_COLLECTION,
    MILVUS_HOST,
    MILVUS_PORT,
    OPENSEARCH_HOST,
    OPENSEARCH_INDEX,
    OPENSEARCH_PARENT_INDEX,
    OPENSEARCH_PORT,
)

logger = logging.getLogger(__name__)


def ensure_opensearch_parent_index(client: OpenSearch) -> bool:
    """Создаёт OpenSearch Parent-индекс."""
    if client.indices.exists(index=OPENSEARCH_PARENT_INDEX):
        return False

    index_body = {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "properties": {
                "id": {"type": "keyword"},
                "full_text": {"type": "text", "index": False},
                "source_file": {"type": "keyword"},
                "service": {"type": "keyword"},
                "header_path": {"type": "keyword"},
            }
        },
    }

    client.indices.create(index=OPENSEARCH_PARENT_INDEX, body=index_body)
    logger.info("Создан parent-индекс: %s", OPENSEARCH_PARENT_INDEX)
    return True


def ensure_opensearch_children_index(client: OpenSearch) -> bool:
    """Создаёт OpenSearch Children-индекс."""
    if client.indices.exists(index=OPENSEARCH_INDEX):
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

    client.indices.create(index=OPENSEARCH_INDEX, body=index_body)
    logger.info("Создан children-индекс: %s", OPENSEARCH_INDEX)
    return True


def ensure_milvus_collection(vector_dim: int) -> Collection:
    """Создаёт коллекцию Milvus."""
    logger.info("Подключение к Milvus: %s:%s", MILVUS_HOST, MILVUS_PORT)
    connections.connect("default", host=MILVUS_HOST, port=MILVUS_PORT)

    if utility.has_collection(MILVUS_COLLECTION):
        collection = Collection(MILVUS_COLLECTION)
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
    collection = Collection(MILVUS_COLLECTION, schema)

    index_params = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {"M": 16, "efConstruction": 128},
    }
    collection.create_index(field_name="vector", index_params=index_params)
    collection.load()

    logger.info("Создана коллекция: %s", MILVUS_COLLECTION)
    return collection


def init_opensearch() -> OpenSearch:
    """Инициализирует OpenSearch-клиент и создаёт ВСЕ индексы."""
    from src.infrastructure.persistence.file_registry import ensure_opensearch_files_index

    logger.info("Подключение к OpenSearch: %s:%s", OPENSEARCH_HOST, OPENSEARCH_PORT)

    client = OpenSearch(
        hosts=[{"host": OPENSEARCH_HOST, "port": OPENSEARCH_PORT}],
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
                index=OPENSEARCH_PARENT_INDEX,
                body={"query": {"term": {"source_file": target_file}}},
                ignore=[404],
            )
        except Exception as e:
            logger.warning("Ошибка удаления parents для %s: %s", target_file, e)

        try:
            os_client.delete_by_query(
                index=OPENSEARCH_INDEX,
                body={"query": {"term": {"source_file": target_file}}},
                ignore=[404],
            )
        except Exception as e:
            logger.warning("Ошибка удаления children из OpenSearch для %s: %s", target_file, e)

        try:

            expr = f'source_file == "{target_file}"'
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
            "_index": OPENSEARCH_PARENT_INDEX,
            "_id": parent["id"],
            "_source": {
                "id": parent["id"],
                "full_text": parent["full_text"],
                "source_file": parent["metadata"].get("source_file"),
                "service": parent["metadata"].get("service"),
                "header_path": parent["metadata"].get("header_path"),
            },
        }
        for parent in parents
    ]

    bulk(client, actions)
    client.indices.refresh(index=OPENSEARCH_PARENT_INDEX)
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
            "_index": OPENSEARCH_INDEX,
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
    client.indices.refresh(index=OPENSEARCH_INDEX)
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

    total_batches = (len(children) + MILVUS_BATCH_SIZE - 1) // MILVUS_BATCH_SIZE
    all_token_lengths: list[int] = []
    overflow_count = 0
    frida_max_tokens = 512

    for batch_idx, start in enumerate(range(0, len(children), MILVUS_BATCH_SIZE)):
        batch = children[start : start + MILVUS_BATCH_SIZE]

        vector_texts = [child["vector_text"] for child in batch]
        texts = [child["text"] for child in batch]
        raw_contents = [child["raw_content"] for child in batch]
        metas = [child["metadata"] for child in batch]
        chunk_types = [child.get("chunk_type", "text") for child in batch]

        prefixed_texts = [f"{DOC_PREFIX}{vt}" for vt in vector_texts]


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
