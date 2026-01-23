"""Модуль извлечения метаданных через Zero-shot NER.

Использует GLiNER для извлечения технических сущностей из DevOps-документации.
При недоступности GLiNER автоматически переключается на regex-based fallback.
Опционально поддерживает LLM-enrichment для повышения качества извлечения.
"""

import json
import logging
import re
import warnings
from typing import Any

from openai import AsyncOpenAI

from src.config import settings
from src.domain.ports.metadata_extractor import MetadataExtractorPort

logger = logging.getLogger(__name__)

warnings.filterwarnings("ignore", category=FutureWarning, module="huggingface_hub")
warnings.filterwarnings("ignore", category=UserWarning, module="transformers")
warnings.filterwarnings("ignore", message=".*max_length.*")

try:
    from gliner import GLiNER

    _GLINER_AVAILABLE = True
except ImportError:
    _GLINER_AVAILABLE = False
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

REGEX_PATTERNS: dict[str, str] = {
    "version": r"(?:v|version[:\s]*)(\d+\.\d+(?:\.\d+)?)",
    "port": r"(?::|port\s*)(\d{2,5})(?:\s|$|/|,)",
    "docker_image": r"(?:image:\s*|FROM\s+)([a-z0-9\-_./]+:[a-z0-9.\-_]+)",
    "k8s_kind": r"kind:\s*(Deployment|Service|Ingress|ConfigMap|Secret|Pod|StatefulSet|DaemonSet)",
    "env_var": r"\$\{?([A-Z_][A-Z0-9_]{2,})\}?",
    "environment": r"\b(production|staging|development|dev|prod|test)\b",
}

NER_SYSTEM_PROMPT = """Ты — NER экстрактор для DevOps документации.
Извлеки технические сущности из текста.

Возможные типы сущностей:
- service: названия сервисов (nginx, redis, postgres, kafka)
- technology: технологии (kubernetes, docker, ansible, terraform)
- command: команды (kubectl, docker-compose, helm, systemctl)
- error_type: типы ошибок (OOMKilled, Connection refused, Timeout)

Верни JSON: {"entities": [{"type": "...", "value": "..."}, ...]}
Если сущностей нет — верни {"entities": []}
Только JSON, без пояснений."""


class GLiNERExtractor(MetadataExtractorPort):
    """Реализация экстрактора метаданных с использованием GLiNER и LLM fallback."""

    def __init__(self):
        self._model = None
        self._api_key = (
            settings.openrouter_api_key.get_secret_value() if settings.openrouter_api_key else None
        )
        self._base_url = settings.openrouter_base_url
        self._ner_limit = settings.ner_text_limit
        self._ner_fallback_model = settings.models.ner_fallback

    def _get_model(self) -> Any:
        """Ленивая загрузка модели GLiNER."""
        if self._model is None and _GLINER_AVAILABLE:
            logger.info("Loading GLiNER model (urchade/gliner_large-v2.1)...")
            try:
                self._model = GLiNER.from_pretrained("urchade/gliner_large-v2.1")

                import torch

                if torch.backends.mps.is_available():
                    self._model = self._model.to("mps")
                    logger.info("GLiNER model loaded on MPS")
                elif torch.cuda.is_available():
                    self._model = self._model.to("cuda")
                    logger.info("GLiNER model loaded on CUDA")
                else:
                    logger.info("GLiNER model loaded on CPU")
            except Exception as e:
                logger.warning("Failed to load GLiNER: %s", e)
        return self._model

    def extract_metadata(
        self,
        text: str,
        labels: list[str] | None = None,
        threshold: float = 0.35,
    ) -> dict[str, list[str]]:
        """Извлекает метаданные комбинированным методом (GLiNER + Regex)."""
        result = self._extract_gliner(text, labels, threshold)
        regex_result = self._extract_regex(text)

        for label, values in regex_result.items():
            if label not in result:
                result[label] = values
            else:
                for v in values:
                    if v not in result[label]:
                        result[label].append(v)
        return result

    def _extract_gliner(
        self, text: str, labels: list[str] | None, threshold: float
    ) -> dict[str, list[str]]:
        """Внутренний метод для извлечения через GLiNER."""
        result: dict[str, list[str]] = {}
        model = self._get_model()
        if not model:
            return result
        try:
            text_truncated = text[: self._ner_limit]
            entities = model.predict_entities(
                text_truncated, labels or DEFAULT_ENTITY_LABELS, threshold=threshold
            )
            for entity in entities:
                label = entity["label"]
                value = entity["text"].strip()
                result.setdefault(label, [])
                if value and value not in result[label]:
                    result[label].append(value)
        except Exception as e:
            logger.warning("GLiNER extraction failed: %s", e)
        return result

    def _extract_regex(self, text: str) -> dict[str, list[str]]:
        """Внутренний метод для извлечения через регулярные выражения."""
        result: dict[str, list[str]] = {}
        for label, pattern in REGEX_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
            if matches:
                unique_values = list({m.lower() if label == "environment" else m for m in matches})
                result[label] = unique_values[:10]
        return result

    async def extract_entities_llm(self, query: str) -> dict[str, list[str]]:
        """Извлекает сущности через LLM (fallback)."""
        if not self._api_key:
            return {}

        try:
            client = AsyncOpenAI(api_key=self._api_key, base_url=self._base_url)
            response = await client.chat.completions.create(
                model=self._ner_fallback_model,
                messages=[
                    {"role": "system", "content": NER_SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                temperature=0.0,
                max_tokens=200,
            )
            content = response.choices[0].message.content or ""

            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                result: dict[str, list[str]] = {}
                for entity in data.get("entities", []):
                    etype = entity.get("type", "").lower()
                    evalue = entity.get("value", "").strip()
                    if etype and evalue:
                        if etype not in result:
                            result[etype] = []
                        if evalue not in result[etype]:
                            result[etype].append(evalue)
                return result
        except json.JSONDecodeError:
            logger.error("Failed to parse LLM NER response as JSON: %s", content)
        except Exception as e:
            logger.warning("LLM NER fallback failed: %s", e)

        return {}
