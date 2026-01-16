"""Модуль извлечения метаданных через Zero-shot NER.

Использует GLiNER для извлечения технических сущностей из DevOps-документации.
При недоступности GLiNER автоматически переключается на regex-based fallback.
Опционально поддерживает LLM-enrichment для повышения качества извлечения.
"""

import logging
import re
import warnings
from typing import Any

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", message=".*max_length.*")

_GLINER_AVAILABLE = False
_gliner_model = None

try:
    from gliner import GLiNER

    _GLINER_AVAILABLE = True
except ImportError:
    logger.info("GLiNER not installed, using regex fallback for metadata extraction")


DEFAULT_ENTITY_LABELS = [
    "service",
    "technology",
    "command",
    "directive",
    "parameter",
    "error_code",
    "file_path",
    "version",
    "environment",
]


def _get_gliner_model() -> Any:
    """Выполняет ленивую загрузку GLiNER модели.

    При первом вызове инициализирует модель urchade/gliner_large-v2.1.
    Использует MPS (Apple GPU) если доступен, иначе CUDA или CPU.
    Последующие вызовы возвращают закешированный экземпляр.

    Returns:
        Загруженная GLiNER модель или None при недоступности.

    """
    global _gliner_model
    if _gliner_model is None and _GLINER_AVAILABLE:
        logger.info("Loading GLiNER model (urchade/gliner_large-v2.1)...")

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
            warnings.filterwarnings("ignore", message=".*max_length.*")
            _gliner_model = GLiNER.from_pretrained("urchade/gliner_large-v2.1")


        try:
            import torch

            if torch.backends.mps.is_available():
                _gliner_model = _gliner_model.to("mps")
                logger.info("GLiNER model loaded on MPS (Apple GPU)")
            elif torch.cuda.is_available():
                _gliner_model = _gliner_model.to("cuda")
                logger.info("GLiNER model loaded on CUDA (NVIDIA GPU)")
            else:
                logger.info("GLiNER model loaded on CPU")
        except Exception as e:
            logger.warning("GPU acceleration failed, using CPU: %s", e)
            logger.info("GLiNER model loaded on CPU")

    return _gliner_model


def extract_metadata_gliner(
    text: str,
    labels: list[str] | None = None,
    threshold: float = 0.35,
) -> dict[str, list[str]]:
    """Извлекает метаданные через GLiNER zero-shot NER.

    Обрабатывает текст нейросетевой моделью GLiNER для извлечения
    именованных сущностей заданных типов.

    Args:
        text: Текст для анализа (обрезается до 2000 символов).
        labels: Список лейблов для извлечения. По умолчанию DEFAULT_ENTITY_LABELS.
        threshold: Минимальный confidence score для фильтрации (0.0-1.0).

    Returns:
        Словарь вида {label: [value1, value2, ...]} с извлечёнными сущностями.
        При ошибке или недоступности GLiNER возвращает пустой словарь.

    """
    if not _GLINER_AVAILABLE:
        return {}

    model = _get_gliner_model()
    if model is None:
        return {}

    labels = labels or DEFAULT_ENTITY_LABELS

    try:
        text_truncated = text[:2000]

        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            warnings.filterwarnings("ignore", category=FutureWarning)
            entities = model.predict_entities(text_truncated, labels, threshold=threshold)

        result: dict[str, list[str]] = {}
        for entity in entities:
            label = entity["label"]
            value = entity["text"].strip()
            if label not in result:
                result[label] = []
            if value and value not in result[label]:
                result[label].append(value)

        return result

    except Exception as e:
        logger.warning("GLiNER extraction failed: %s", e)
        return {}


REGEX_PATTERNS: dict[str, str] = {
    "version": r"(?:v|version[:\s]*)(\d+\.\d+(?:\.\d+)?)",
    "port": r"(?::|port\s*)(\d{2,5})(?:\s|$|/|,)",
    "docker_image": r"(?:image:\s*|FROM\s+)([a-z0-9\-_./]+:[a-z0-9.\-_]+)",
    "k8s_kind": r"kind:\s*(Deployment|Service|Ingress|ConfigMap|Secret|Pod|StatefulSet|DaemonSet)",
    "env_var": r"\$\{?([A-Z_][A-Z0-9_]{2,})\}?",
    "environment": r"\b(production|staging|development|dev|prod|test)\b",
}


def extract_metadata_regex(text: str) -> dict[str, list[str]]:
    """Извлекает метаданные через регулярные выражения.

    Используется как fallback при недоступности GLiNER или
    для дополнения результатов нейросетевого извлечения.

    Args:
        text: Текст для анализа.

    Returns:
        Словарь вида {label: [value1, value2, ...]} с найденными паттернами.
        Значения нормализуются и ограничиваются до 10 на категорию.

    """
    result: dict[str, list[str]] = {}

    for label, pattern in REGEX_PATTERNS.items():
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        if matches:
            unique_values = list({m.lower() if label == "environment" else m for m in matches})
            result[label] = unique_values[:10]

    return result


NER_SYSTEM_PROMPT = """Ты — NER экстрактор для DevOps документации. /no_think
Извлеки технические сущности из запроса пользователя.

Возможные типы сущностей:
- service: названия сервисов (nginx, redis, postgres, kafka)
- technology: технологии (kubernetes, docker, ansible, terraform)
- command: команды (kubectl, docker-compose, helm, systemctl)
- error_type: типы ошибок (OOMKilled, Connection refused, Timeout)

Верни JSON: {"entities": [{"type": "...", "value": "..."}]}
Если сущностей нет — верни {"entities": []}
Только JSON, без пояснений."""


async def extract_entities_llm(query: str) -> dict[str, list[str]]:
    """Извлекает сущности через LLM (OpenRouter) при неудаче GLiNER.

    Вызывается когда основные методы извлечения вернули пустой или
    слабый результат. Использует легковесную модель через OpenRouter API.

    Args:
        query: Текст запроса пользователя.

    Returns:
        Словарь вида {entity_type: [value1, value2, ...]} с извлечёнными сущностями.
        При ошибке возвращает пустой словарь.

    """
    try:
        from openai import AsyncOpenAI

        from src.config import (
            NER_FALLBACK_MODEL,
            OPENROUTER_API_KEY,
            OPENROUTER_BASE_URL,
        )

        if not OPENROUTER_API_KEY:
            logger.warning("OpenRouter API key not set, skipping LLM fallback")
            return {}

        client = AsyncOpenAI(
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
        )

        response = await client.chat.completions.create(
            model=NER_FALLBACK_MODEL,
            messages=[
                {"role": "system", "content": NER_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=200,
        )

        content = response.choices[0].message.content or ""

        import json

        start = content.find("{")
        end = content.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = content[start:end]
            data = json.loads(json_str)

            result: dict[str, list[str]] = {}
            for entity in data.get("entities", []):
                etype = entity.get("type", "").lower()
                evalue = entity.get("value", "").strip()
                if etype and evalue:
                    if etype not in result:
                        result[etype] = []
                    if evalue not in result[etype]:
                        result[etype].append(evalue)

            if result:
                logger.info("LLM fallback extracted entities: %s", result)
            return result

        return {}

    except Exception as e:
        logger.warning("LLM fallback extraction failed: %s", e)
        return {}


def extract_metadata(
    text: str,
    use_gliner: bool = True,
    labels: list[str] | None = None,
) -> dict[str, list[str]]:
    """Извлекает метаданные из текста комбинированным методом.

    Использует GLiNER как основной инструмент и дополняет результаты
    regex-паттернами для максимального покрытия извлечения.

    Args:
        text: Текст для анализа.
        use_gliner: Использовать GLiNER (True) или только regex (False).
        labels: Список лейблов для GLiNER-извлечения.

    Returns:
        Объединённый словарь {label: [values]} из всех источников.

    """
    result: dict[str, list[str]] = {}

    if use_gliner and _GLINER_AVAILABLE:
        gliner_result = extract_metadata_gliner(text, labels)
        if gliner_result:
            result.update(gliner_result)

    regex_result = extract_metadata_regex(text)
    for label, values in regex_result.items():
        if label not in result:
            result[label] = values
        else:
            for v in values:
                if v not in result[label]:
                    result[label].append(v)

    return result


async def extract_metadata_with_llm_fallback(
    text: str,
    use_gliner: bool = True,
    labels: list[str] | None = None,
) -> dict[str, list[str]]:
    """Извлекает метаданные с LLM-обогащением при слабых результатах.

    Предназначена для использования при индексации документов (offline),
    когда допустимы дополнительные затраты времени на LLM-вызовы.
    При отсутствии "сильных" сущностей (service, technology, command)
    автоматически запрашивает LLM для повышения качества.

    Args:
        text: Текст для анализа.
        use_gliner: Использовать GLiNER перед LLM fallback.
        labels: Список лейблов для GLiNER-извлечения.

    Returns:
        Обогащённый словарь {label: [values]} с метаданными.

    """
    result = extract_metadata(text, use_gliner, labels)

    strong_types = {"service", "technology", "command"}
    has_strong = any(t in result for t in strong_types)

    if not has_strong:
        logger.debug("GLiNER/regex weak, enriching with LLM...")
        llm_result = await extract_entities_llm(text[:2000])

        for etype, values in llm_result.items():
            if etype not in result:
                result[etype] = values
            else:
                for v in values:
                    if v not in result[etype]:
                        result[etype].append(v)

    return result


def is_gliner_available() -> bool:
    """Проверяет доступность GLiNER в текущем окружении.

    Returns:
        True если GLiNER установлен и готов к использованию.

    """
    return _GLINER_AVAILABLE
