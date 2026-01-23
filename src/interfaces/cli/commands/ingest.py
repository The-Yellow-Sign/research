"""CLI команда: инкрементальная индексация документов.

Entry-point для пайплайна загрузки данных в RAG-систему.
Координирует работу модулей file_registry и indexer.
Поддерживает опциональное LLM-обогащение метаданных.
"""

import argparse
import asyncio
import logging

from sentence_transformers import SentenceTransformer

from src.config import settings
from src.config.logging_config import setup_logging
from src.infrastructure import process_specific_files
from src.infrastructure.persistence import (
    delete_by_source_file,
    detect_file_changes,
    ensure_milvus_collection,
    index_data,
    init_opensearch,
    update_file_hashes,
)
from src.infrastructure.persistence.file_registry import ensure_opensearch_files_index
from src.infrastructure.persistence.splitter import process_specific_files_async

logger = logging.getLogger(__name__)


def _init_ingest_clients():
    """Инициализирует клиенты и модель для индексации."""
    setup_logging()
    logger.info("Загрузка модели эмбеддингов: %s", settings.models.embedding)
    model = SentenceTransformer(settings.models.embedding)

    os_client = init_opensearch()
    milvus_collection = ensure_milvus_collection(model.get_sentence_embedding_dimension())
    return model, os_client, milvus_collection


def _handle_force_reindex(os_client, force_reindex: bool, label_prefix: str = "") -> None:
    """Очищает реестр файлов при необходимости."""
    if force_reindex:
        logger.info("%sПринудительная переиндексация: очистка реестра файлов", label_prefix)
        try:
            os_client.indices.delete(index=settings.opensearch_files_index, ignore=[404])
            ensure_opensearch_files_index(os_client)
        except Exception as e:
            logger.error("Ошибка при очистке реестра файлов: %s", e)


def _get_rel_paths(files):
    """Преобразует список путей в относительные для индекса."""
    rel_paths = []
    for f in files:
        try:
            rel_paths.append(str(f.relative_to(settings.source_dir)))
        except ValueError:
            rel_paths.append(f.name)
    return rel_paths


def run_ingest(force_reindex: bool = False) -> None:
    """Запускает синхронный пайплайн инкрементальной индексации."""
    model, os_client, milvus_collection = _init_ingest_clients()
    _handle_force_reindex(os_client, force_reindex)

    new_or_modified, unchanged, deleted_paths = detect_file_changes(os_client, settings.source_dir)

    if not new_or_modified and not deleted_paths:
        logger.info("Нет изменений. Индексация не требуется.")
        return

    if deleted_paths:
        delete_by_source_file(os_client, milvus_collection, deleted_paths)

    if new_or_modified:
        modified_rel_paths = _get_rel_paths(new_or_modified)
        delete_by_source_file(os_client, milvus_collection, modified_rel_paths)

        parents, children = process_specific_files(new_or_modified)
        index_data(os_client, milvus_collection, model, parents, children)

    update_file_hashes(os_client, new_or_modified, deleted_paths)
    logger.info("Инкрементальная загрузка завершена успешно")


async def run_ingest_async(force_reindex: bool = False) -> None:
    """Запускает асинхронный пайплайн с LLM-обогащением метаданных."""
    model, os_client, milvus_collection = _init_ingest_clients()
    _handle_force_reindex(os_client, force_reindex, "LLM enrichment: ")

    new_or_modified, unchanged, deleted_paths = detect_file_changes(os_client, settings.source_dir)

    if not new_or_modified and not deleted_paths:
        logger.info("Нет изменений. Индексация не требуется.")
        return

    if deleted_paths:
        delete_by_source_file(os_client, milvus_collection, deleted_paths)

    if new_or_modified:
        modified_rel_paths = _get_rel_paths(new_or_modified)
        delete_by_source_file(os_client, milvus_collection, modified_rel_paths)

        logger.info("Индексация с LLM enrichment для %d файлов...", len(new_or_modified))
        parents, children = await process_specific_files_async(new_or_modified)
        index_data(os_client, milvus_collection, model, parents, children)

    update_file_hashes(os_client, new_or_modified, deleted_paths)
    logger.info("Индексация с LLM enrichment завершена успешно")


def main() -> None:
    """CLI entry point для команды ingest."""
    parser = argparse.ArgumentParser(description="Инкрементальная индексация RAG")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная переиндексация всех файлов",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Использовать LLM для обогащения метаданных (медленнее, но качественнее)",
    )
    args = parser.parse_args()

    if args.llm:
        asyncio.run(run_ingest_async(force_reindex=args.force))
    else:
        run_ingest(force_reindex=args.force)


if __name__ == "__main__":
    main()
