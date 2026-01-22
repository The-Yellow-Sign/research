"""Модуль оценки RAG-системы с использованием RAGAS.

Предоставляет инструменты для автоматической оценки качества
генерации ответов: context precision, context recall, faithfulness.
Поддерживает кастомные русскоязычные промпты.
"""

import logging
from typing import Any

from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import SingleTurnSample
from ragas.metrics._context_precision import ContextPrecision
from ragas.metrics._context_recall import LLMContextRecall
from ragas.metrics._faithfulness import Faithfulness

from src.config.settings import settings
from src.evaluation.base_evaluator import BaseRagasEvaluator

logger = logging.getLogger(__name__)


class RagasEvaluator(BaseRagasEvaluator):
    """Оценщик систем RAG на основе RAGAS v0.4+."""

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

        # Only return metric columns to avoid Pydantic serialization errors with raw data columns
        scores = df[metric_names].to_dict(orient="records")

        summary = {}
        for col in metric_names:
            if col in df.columns and not df[col].empty:
                summary[col] = float(df[col].mean())
            else:
                summary[col] = 0.0

        logger.info("RAGAS Evaluation Complete.")
        return {"scores": scores, "summary": summary}
