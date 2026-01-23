"""Базовый класс для оценщиков RAGAS.

Содержит общую логику инициализации LLM, embeddings и загрузки промптов.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.run_config import RunConfig
from sentence_transformers import SentenceTransformer

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddings(BaseRagasEmbeddings):
    """RAGAS-совместимая обертка для SentenceTransformer."""

    def __init__(self, model_name: str):
        self.model = model_name
        self.transformer = SentenceTransformer(model_name)
        self._run_config = RunConfig()

    @property
    def run_config(self) -> RunConfig:
        """Возвращает конфигурацию запуска для RAGAS."""
        return self._run_config

    @run_config.setter
    def run_config(self, value: RunConfig) -> None:
        """Устанавливает конфигурацию запуска."""
        self._run_config = value

    def embed_query(self, text: str) -> list[float]:
        """Генерирует эмбеддинг для запроса."""
        return self.transformer.encode(text, normalize_embeddings=True).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Генерирует эмбеддинги для документов."""
        embeddings = self.transformer.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    async def aembed_query(self, text: str) -> list[float]:
        """Асинхронно генерирует эмбеддинг для запроса."""
        return self.embed_query(text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        """Асинхронно генерирует эмбеддинги для документов."""
        return self.embed_documents(texts)


class BaseRagasEvaluator(ABC):
    """Абстрактный базовый класс для RAGAS-оценщиков."""

    def __init__(
        self,
        model: str | None = None,
        prompts_path: Path | None = None,
    ) -> None:
        """Инициализация.

        Args:
            model: Имя модели LLM-судьи.
            prompts_path: Путь к YAML файлу с промптами.

        """
        self.model = model or settings.models.eval_judge
        self.prompts_path = prompts_path or Path("src/evaluation/prompts/ragas_prompts.yaml")

        self._init_llm()
        self._init_metrics()
        self._apply_custom_prompts()

        logger.info("%s initialized: model=%s", self.__class__.__name__, self.model)

    def _init_llm(self) -> None:
        """Инициализирует LLM и embeddings для RAGAS."""
        self.llm = ChatOpenAI(
            model=self.model,
            api_key=settings.openrouter_api_key.get_secret_value(),
            base_url=settings.openrouter_base_url,
            temperature=0,
            timeout=settings.ragas_timeout,
            max_retries=settings.ragas_max_retries,
        )
        self.ragas_llm = LangchainLLMWrapper(self.llm)
        self.ragas_embeddings = SentenceTransformerEmbeddings(settings.models.embedding)

    @abstractmethod
    def _init_metrics(self) -> None:
        """Инициализирует метрики. Реализуется в подклассах."""
        ...

    def _load_prompts_from_yaml(self) -> dict:
        """Загружает кастомные инструкции из YAML."""
        if not self.prompts_path.exists():
            logger.warning("Prompts file not found at %s, using RAGAS defaults.", self.prompts_path)
            return {}

        try:
            with open(self.prompts_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                prompts = data.get("prompts", {})
                logger.info("Loaded %d custom prompts from YAML.", len(prompts))
                return prompts
        except Exception:
            logger.exception("Error loading prompts yaml")
            return {}

    def _apply_custom_prompts(self) -> None:
        """Внедряет инструкции из YAML в объекты промптов метрик."""
        custom_prompts = self._load_prompts_from_yaml()
        if not custom_prompts:
            return

        for metric in self.metrics:
            try:
                current_prompts = metric.get_prompts()
                updates = {}

                for internal_prompt_name, prompt_obj in current_prompts.items():
                    if internal_prompt_name in custom_prompts:
                        prompt_obj.instruction = custom_prompts[internal_prompt_name]
                        updates[internal_prompt_name] = prompt_obj
                        logger.debug(
                            "Applied custom instruction for '%s.%s'",
                            metric.name,
                            internal_prompt_name,
                        )

                if updates:
                    metric.set_prompts(**updates)

            except Exception:
                logger.warning("Failed to update prompts for metric %s", metric.name, exc_info=True)

    @abstractmethod
    async def evaluate_batch(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        """Запускает оценку батча данных."""
        ...
