"""Модуль реестра файлов для отслеживания изменений.

Отвечает за:
- Хэширование файлов через SHA256
- Хранение хэшей в OpenSearch
- Детектирование новых, изменённых и удалённых файлов
"""

import datetime
import hashlib
import logging
from pathlib import Path

from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk, scan

from src.config import SOURCE_DIR

logger = logging.getLogger(__name__)

OPENSEARCH_FILES_INDEX = "rag_files_registry"


def calculate_file_hash(filepath: Path) -> str:
    """Вычисляет SHA256-хэш содержимого файла."""
    hasher = hashlib.sha256()
    with filepath.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def ensure_opensearch_files_index(client: OpenSearch) -> bool:
    """Создаёт индекс реестра файлов в OpenSearch."""
    if client.indices.exists(index=OPENSEARCH_FILES_INDEX):
        return False

    index_body = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
        },
        "mappings": {
            "properties": {
                "file_path": {"type": "keyword"},
                "file_hash": {"type": "keyword"},
                "last_updated": {"type": "date"},
            }
        },
    }

    client.indices.create(index=OPENSEARCH_FILES_INDEX, body=index_body)
    logger.info("Создан индекс реестра файлов: %s", OPENSEARCH_FILES_INDEX)
    return True


def load_file_hashes(client: OpenSearch) -> dict[str, str]:
    """Загружает сохранённые хэши файлов из OpenSearch."""
    if not client.indices.exists(index=OPENSEARCH_FILES_INDEX):
        return {}

    logger.info("Загрузка хэшей файлов из БД...")
    stored_hashes = {}

    try:
        for hit in scan(client, index=OPENSEARCH_FILES_INDEX, query={"query": {"match_all": {}}}):
            source = hit["_source"]

            path = hit["_id"]
            file_hash = source.get("file_hash")
            if path and file_hash:
                stored_hashes[path] = file_hash

    except Exception as e:
        logger.warning("Ошибка при чтении реестра файлов: %s. Начинаем с пустого состояния.", e)
        return {}

    return stored_hashes


def update_file_hashes(client: OpenSearch, files: list[Path], deleted_paths: list[str]) -> None:
    """Обновляет реестр файлов в OpenSearch (bulk update/delete)."""
    actions = []

    for path in deleted_paths:
        actions.append(
            {
                "_op_type": "delete",
                "_index": OPENSEARCH_FILES_INDEX,
                "_id": path,
            }
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for filepath in files:
        try:
            rel_path = str(filepath.relative_to(SOURCE_DIR))
        except ValueError:
            rel_path = filepath.name

        file_hash = calculate_file_hash(filepath)

        actions.append(
            {
                "_op_type": "index",
                "_index": OPENSEARCH_FILES_INDEX,
                "_id": rel_path,
                "_source": {"file_path": rel_path, "file_hash": file_hash, "last_updated": now},
            }
        )

    if actions:
        success, failed = bulk(client, actions, stats_only=True, refresh=True)
        logger.info(
            "Реестр файлов обновлен: %d успешно, %d ошибок (удалено: %d, обновлено: %d)",
            success,
            failed,
            len(deleted_paths),
            len(files),
        )
    else:
        logger.info("Нет изменений для записи в реестр файлов.")


def detect_file_changes(
    client: OpenSearch,
    source_dir: Path,
) -> tuple[list[Path], list[Path], list[str]]:
    """Определяет изменения в файлах, сравнивая с БД."""
    stored_hashes = load_file_hashes(client)

    current_files = list(source_dir.glob("**/*.md"))

    current_files_map = {}
    for f in current_files:
        try:
            rel_path = str(f.relative_to(source_dir))
            current_files_map[rel_path] = f
        except ValueError:
            continue

    current_paths = set(current_files_map.keys())
    stored_paths = set(stored_hashes.keys())

    deleted_paths = stored_paths - current_paths

    new_or_modified: list[Path] = []
    unchanged: list[Path] = []

    for rel_path, filepath in current_files_map.items():
        current_hash = calculate_file_hash(filepath)
        stored_hash = stored_hashes.get(rel_path)

        if stored_hash is None:
            logger.info("Новый файл: %s", rel_path)
            new_or_modified.append(filepath)
        elif current_hash != stored_hash:
            logger.info("Изменённый файл: %s", rel_path)
            new_or_modified.append(filepath)
        else:
            unchanged.append(filepath)

    logger.info(
        "Обнаружено изменений: %d новых/изменённых, %d неизменённых, %d удалённых",
        len(new_or_modified),
        len(unchanged),
        len(deleted_paths),
    )

    return new_or_modified, unchanged, list(deleted_paths)
