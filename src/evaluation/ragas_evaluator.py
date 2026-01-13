"""Модуль оценки RAG-системы с использованием RAGAS.

Предоставляет инструменты для автоматической оценки качества
генерации ответов: context precision, context recall, faithfulness.
Поддерживает кастомные русскоязычные промпты.
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from langchain_openai import ChatOpenAI
from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.metrics._context_precision import ContextPrecision
from ragas.metrics._context_recall import LLMContextRecall
from ragas.metrics._faithfulness import Faithfulness
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


class RagasEvaluator:
    """Оценщик систем RAG на основе RAGAS v0.4+."""

    def __init__(self, model: str | None = None, prompts_path: Path | None = None) -> None:
        """Инициализация.

        Args:
            model: Имя модели LLM-судьи.
            prompts_path: Путь к YAML файлу с промптами.

        """
        self.model = model or settings.eval_judge_model
        self.prompts_path = prompts_path or Path("src/evaluation/prompts/ragas_prompts.yaml")

        self.llm = ChatOpenAI(
            model=self.model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            temperature=0,
            timeout=settings.ragas_timeout,
            max_retries=settings.ragas_max_retries,
        )
        self.ragas_llm = LangchainLLMWrapper(self.llm)
        self.ragas_embeddings = SentenceTransformerEmbeddings(settings.embedding_model_name)

        self._init_metrics()

        logger.info("RagasEvaluator initialized: model=%s", self.model)

    def _init_metrics(self) -> None:
        """Инициализирует метрики RAGAS v0.4+."""
        self.faithfulness = Faithfulness(llm=self.ragas_llm)
        self.context_recall = LLMContextRecall(llm=self.ragas_llm)
        self.context_precision = ContextPrecision(llm=self.ragas_llm)

        self.metrics = [
            self.faithfulness,
            self.context_recall,
            self.context_precision,
        ]

        self._apply_custom_prompts()

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
        """Внедряет инструкции из YAML в объекты промптов метрик.

        Маппинг YAML ключей на внутренние имена промптов RAGAS:
        - statement_generator_prompt -> Faithfulness
        - n_l_i_statement_prompt -> Faithfulness
        - context_recall_classification_prompt -> LLMContextRecall
        - context_precision_prompt -> ContextPrecision
        """
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

    def prepare_dataset(self, items: list[dict[str, Any]]) -> EvaluationDataset:
        """Подготавливает EvaluationDataset в формате RAGAS v0.4+.

        Args:
            items: Список словарей с результатами оценки.

        Returns:
            EvaluationDataset совместимый с RAGAS.

        """
        samples = []

        for item in items:
            contexts = item.get("retrieved_contexts", [])
            ctx_list = []
            for c in contexts:
                if isinstance(c, dict):
                    ctx_list.append(c.get("content", ""))
                elif hasattr(c, "content"):
                    ctx_list.append(c.content)
                else:
                    ctx_list.append(str(c))

            gt = item.get("expected_answer", "")
            if isinstance(gt, list) and gt:
                gt_str = str(gt[0])
            else:
                gt_str = str(gt)

            sample = SingleTurnSample(
                user_input=item.get("question", ""),
                response=item.get("generated_answer", ""),
                reference=gt_str,
                retrieved_contexts=ctx_list,
            )
            samples.append(sample)

        return EvaluationDataset(samples=samples)

    async def evaluate_batch(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Запускает оценку батча данных.

        Args:
            items: Список элементов для оценки.

        Returns:
            Словарь с оценками и сводкой.

        """
        if not items:
            return {"scores": [], "summary": {}}

        dataset = self.prepare_dataset(items)
        logger.info("Running RAGAS evaluation on %d items...", len(items))

        run_config = RunConfig(
            timeout=settings.ragas_timeout,
            max_retries=settings.ragas_max_retries,
            max_wait=settings.ragas_timeout // 5,
            max_workers=settings.ragas_max_workers,
        )

        try:
            result = evaluate(
                dataset=dataset,
                metrics=self.metrics,
                llm=self.ragas_llm,
                embeddings=self.ragas_embeddings,
                run_config=run_config,
                raise_exceptions=False,
            )
            df = result.to_pandas()

        except Exception:
            logger.exception("FATAL: RAGAS evaluation crashed")
            return {"scores": [{} for _ in items], "summary": {}}

        metric_names = [m.name for m in self.metrics]

        for col in metric_names:
            if col in df.columns:
                df[col] = df[col].fillna(0.0)

        scores = df.to_dict(orient="records")

        summary = {}
        for col in metric_names:
            if col in df.columns and not df[col].empty:
                summary[col] = float(df[col].mean())
            else:
                summary[col] = 0.0

        logger.info("RAGAS Evaluation Complete.")
        return {"scores": scores, "summary": summary}
