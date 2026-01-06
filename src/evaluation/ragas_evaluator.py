"""RAGAS-оценка системы RAG.

Использует библиотеку RAGAS (v0.4+) для стандартизированных метрик.
Исправлена совместимость с SingleTurnSample (ground_truth должен быть str).
"""

import logging
from pathlib import Path
from typing import Any

import yaml
from datasets import Dataset
from langchain_openai import ChatOpenAI
from ragas import RunConfig, evaluate
from ragas.embeddings.base import BaseRagasEmbeddings
from ragas.llms import LangchainLLMWrapper
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)
from sentence_transformers import SentenceTransformer

from src.config.settings import settings

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddings(BaseRagasEmbeddings):
    """RAGAS-совместимая обертка для SentenceTransformer."""

    def __init__(self, model_name: str):
        self.model = model_name
        self.transformer = SentenceTransformer(model_name)

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
    """Оценщик систем RAG на основе RAGAS."""

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

        logger.info("RagasEvaluator initialized: model=%s", self.model)

    def _load_prompts_from_yaml(self) -> dict:
        """Загружает кастомные инструкции из YAML."""
        if not self.prompts_path.exists():
            logger.warning(f"Prompts file not found at {self.prompts_path}, using RAGAS defaults.")
            return {}

        try:
            with open(self.prompts_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                prompts = data.get("prompts", {})
                logger.info(f"Loaded {len(prompts)} custom prompts from YAML.")
                return prompts
        except Exception as e:
            logger.error(f"Error loading prompts yaml: {e}")
            return {}

    def _apply_custom_prompts(self, metrics: list):
        """Внедряет инструкции из YAML в объекты промптов метрик."""
        custom_prompts = self._load_prompts_from_yaml()
        if not custom_prompts:
            return

        key_mapping = {
            "faithfulness_prompt": "faithfulness_prompt",
            "context_recall_prompt": "context_recall_prompt",
            "context_precision_prompt": "context_precision_prompt",
            "answer_relevancy_prompt": "question_generation",
            "question_generation": "question_generation",
        }

        for metric in metrics:
            try:
                current_prompts = metric.get_prompts()
                updates = {}

                for ragas_internal_name, prompt_obj in current_prompts.items():
                    yaml_text = custom_prompts.get(ragas_internal_name)

                    if not yaml_text:
                        for yaml_key, internal_key in key_mapping.items():
                            if internal_key == ragas_internal_name and yaml_key in custom_prompts:
                                yaml_text = custom_prompts[yaml_key]
                                break

                    if yaml_text:
                        prompt_obj.instruction = yaml_text
                        updates[ragas_internal_name] = prompt_obj
                        logger.debug(f"Applied custom instruction for '{ragas_internal_name}'")

                if updates:
                    metric.set_prompts(**updates)

            except Exception as e:
                logger.warning("Failed to update prompts for metric %s: %s", metric.name, e)

    def prepare_dataset(self, items: list[dict[str, Any]]) -> Dataset:
        """Подготавливает HF Dataset в формате, ожидаемом RAGAS.

        Args:
            items: Список словарей с результатами оценки.

        Returns:
            Dataset совместимый с RAGAS.

        """
        data = {
            "question": [],
            "answer": [],
            "ground_truth": [],
            "contexts": [],
        }

        for item in items:
            data["question"].append(item.get("question", ""))
            data["answer"].append(item.get("generated_answer", ""))

            gt = item.get("expected_answer", "")
            if isinstance(gt, list) and gt:
                gt_str = str(gt[0])
            else:
                gt_str = str(gt)

            data["ground_truth"].append(gt_str)

            contexts = item.get("retrieved_contexts", [])
            ctx_list = []
            for c in contexts:
                if isinstance(c, dict):
                    ctx_list.append(c.get("content", ""))
                elif hasattr(c, "content"):
                    ctx_list.append(c.content)
                else:
                    ctx_list.append(str(c))
            data["contexts"].append(ctx_list)

        return Dataset.from_dict(data)

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

        metrics = [faithfulness, answer_relevancy, context_recall, context_precision]

        self._apply_custom_prompts(metrics)

        run_config = RunConfig(
            timeout=settings.ragas_timeout,
            max_retries=settings.ragas_max_retries,
            max_wait=settings.ragas_timeout // 5,
            max_workers=settings.ragas_max_workers,
        )

        try:
            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=self.ragas_llm,
                embeddings=self.ragas_embeddings,
                run_config=run_config,
                raise_exceptions=False,
            )
            df = result.to_pandas()

        except Exception:
            logger.exception("FATAL: RAGAS evaluation crashed")
            return {"scores": [{} for _ in items], "summary": {}}

        metric_names = [m.name for m in metrics]
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
