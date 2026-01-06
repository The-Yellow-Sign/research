"""CLI команда: инкрементальная индексация.

Entry-point для пайплайна загрузки данных в RAG-систему.
Координирует работу file_registry и indexer модулей.
"""

import argparse
import logging

from sentence_transformers import SentenceTransformer

from src.config import EMBEDDING_MODEL_NAME, SOURCE_DIR
from src.config.logging_config import setup_logging
from src.infrastructure import process_specific_files
from src.infrastructure.persistence import (
    OPENSEARCH_FILES_INDEX,
    delete_by_source_file,
    detect_file_changes,
    ensure_milvus_collection,
    index_data,
    init_opensearch,
    update_file_hashes,
)
from src.infrastructure.persistence.file_registry import ensure_opensearch_files_index

logger = logging.getLogger(__name__)


def run_ingest(force_reindex: bool = False) -> None:
    """Запускает пайплайн инкрементальной загрузки.

    Args:
        force_reindex: Если True, очищает реестр и переиндексирует всё.

    """
    setup_logging()
    logger.info("Загрузка модели эмбеддингов: %s", EMBEDDING_MODEL_NAME)
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)

    os_client = init_opensearch()
    milvus_collection = ensure_milvus_collection(model.get_sentence_embedding_dimension())

    if force_reindex:
        logger.info("Принудительная переиндексация: очистка реестра файлов")
        try:
            os_client.indices.delete(index=OPENSEARCH_FILES_INDEX, ignore=[404])
            ensure_opensearch_files_index(os_client)
        except Exception as e:
            logger.error("Ошибка при очистке реестра файлов: %s", e)

    new_or_modified, unchanged, deleted_paths = detect_file_changes(os_client, SOURCE_DIR)

    if not new_or_modified and not deleted_paths:
        logger.info("Нет изменений. Индексация не требуется.")
        return

    if deleted_paths:
        delete_by_source_file(os_client, milvus_collection, deleted_paths)

    if new_or_modified:
        modified_rel_paths = []
        for f in new_or_modified:
            try:
                modified_rel_paths.append(str(f.relative_to(SOURCE_DIR)))
            except ValueError:
                modified_rel_paths.append(f.name)

        delete_by_source_file(os_client, milvus_collection, modified_rel_paths)

        parents, children = process_specific_files(new_or_modified)
        index_data(os_client, milvus_collection, model, parents, children)

    all_current_files = new_or_modified
    update_file_hashes(os_client, all_current_files, deleted_paths)

    logger.info("Инкрементальная загрузка завершена успешно")


def main() -> None:
    """CLI entry point для команды ingest."""
    parser = argparse.ArgumentParser(description="Инкрементальная индексация RAG")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная переиндексация всех файлов",
    )
    args = parser.parse_args()

    run_ingest(force_reindex=args.force)


if __name__ == "__main__":
    main()
