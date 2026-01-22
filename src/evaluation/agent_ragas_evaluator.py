"""Модуль оценки Agentic RAG с использованием RAGAS.

Дополнительные метрики для агентов:
- ToolCallAccuracy — точность вызова инструментов
- AgentGoalAccuracy — достиг ли агент цели
"""

import json
import logging
from typing import Any

from ragas import EvaluationDataset, RunConfig, evaluate
from ragas.dataset_schema import MultiTurnSample
from ragas.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from ragas.metrics import (
    AnswerRelevancy,
    ContextPrecision,
    ContextRecall,
    Faithfulness,
)
from ragas.metrics._goal_accuracy import AgentGoalAccuracyWithoutReference
from ragas.metrics._tool_call_accuracy import ToolCallAccuracy

from src.config.settings import settings
from src.evaluation.base_evaluator import BaseRagasEvaluator

logger = logging.getLogger(__name__)


class AgentRagasEvaluator(BaseRagasEvaluator):
    """Оценщик Agentic RAG на основе RAGAS v0.4+."""

    def _init_metrics(self) -> None:
        """Инициализирует метрики для агентов."""
        self.tool_call_accuracy = ToolCallAccuracy()
        self.agent_goal_accuracy = AgentGoalAccuracyWithoutReference(llm=self.ragas_llm)

        self.faithfulness = Faithfulness(llm=self.ragas_llm)
        self.answer_relevancy = AnswerRelevancy(
            llm=self.ragas_llm, embeddings=self.ragas_embeddings
        )
        self.context_precision = ContextPrecision(llm=self.ragas_llm)
        self.context_recall = ContextRecall(llm=self.ragas_llm)

        self.metrics = [
            self.agent_goal_accuracy,
            self.faithfulness,
            self.answer_relevancy,
            self.context_precision,
            self.context_recall,
        ]

    def prepare_datasets(
        self, items: list[dict[str, Any]]
    ) -> tuple[EvaluationDataset, EvaluationDataset]:
        """Подготавливает датасеты для MultiTurn и SingleTurn оценки.

        Args:
            items: Список словарей с результатами агента.

        Returns:
            (multi_turn_dataset, single_turn_dataset)

        """
        from ragas.dataset_schema import SingleTurnSample

        multi_samples = []
        single_samples = []

        for item in items:
            user_input_str = item.get("question", "")
            reference = item.get("ground_truth", "")
            agent_answer = item.get("predicted_answer", "")
            tool_calls_data = item.get("tool_calls", [])
            expected_tools = item.get("expected_tools", [])
            raw_contexts = item.get("retrieved_contexts", [])
            retrieved_contexts = []
            for ctx in raw_contexts:
                if isinstance(ctx, dict):
                    retrieved_contexts.append(ctx.get("content") or str(ctx))
                else:
                    retrieved_contexts.append(str(ctx))

            messages = [HumanMessage(content=user_input_str)]

            for tc in tool_calls_data:
                args = tc.get("args", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except Exception:
                        args = {"raw_args": args}

                tool_call = ToolCall(
                    name=tc.get("name", "unknown"),
                    args=args if isinstance(args, dict) else {},
                )
                ai_msg = AIMessage(content="", tool_calls=[tool_call])
                messages.append(ai_msg)

                tool_result = ToolMessage(content=str(tc.get("result") or ""))
                messages.append(tool_result)

            messages.append(AIMessage(content=agent_answer))

            reference_tool_calls = [ToolCall(name=t, args={}) for t in expected_tools]

            multi_sample = MultiTurnSample(
                user_input=messages,
                reference=reference,
                reference_tool_calls=reference_tool_calls,
                retrieved_contexts=retrieved_contexts,
            )
            multi_samples.append(multi_sample)

            single_sample = SingleTurnSample(
                user_input=user_input_str,
                response=agent_answer,
                reference=reference,
                retrieved_contexts=retrieved_contexts,
            )
            single_samples.append(single_sample)

        return EvaluationDataset(samples=multi_samples), EvaluationDataset(samples=single_samples)

    def _evaluate_part(
        self,
        dataset: EvaluationDataset,
        metrics: list[Any],
        run_config: RunConfig,
        scores_list: list[dict[str, Any]],
        part_name: str,
    ) -> None:
        """Запускает оценку для определенной части (MultiTurn/SingleTurn)."""
        if not metrics:
            return

        logger.info("Evaluating %s metrics: %s", part_name, [m.name for m in metrics])
        try:
            result = evaluate(
                dataset=dataset,
                metrics=metrics,
                llm=self.ragas_llm,
                run_config=run_config,
                raise_exceptions=False,
            )
            df = result.to_pandas()

            if not df.empty:
                for idx, row in df.iterrows():
                    if idx < len(scores_list):
                        for col in df.columns:
                            if col in [m.name for m in metrics]:
                                val = row[col]
                                scores_list[idx][col] = float(val) if val is not None else 0.0

        except Exception:
            logger.exception("Error in %s evaluation", part_name)

    def _calculate_summary(
        self, scores_list: list[dict[str, Any]], total_items: int
    ) -> dict[str, float]:
        """Вычисляет средние оценки."""
        summary = {}
        all_metric_names = [m.name for m in self.metrics]

        sums = dict.fromkeys(all_metric_names, 0.0)
        counts = dict.fromkeys(all_metric_names, 0)

        for score_dict in scores_list:
            for name in all_metric_names:
                if name in score_dict:
                    sums[name] += score_dict[name]
                    counts[name] += 1

        for name in all_metric_names:
            if counts[name] > 0:
                summary[name] = sums[name] / total_items
            else:
                summary[name] = 0.0
        return summary

    async def evaluate_batch(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Запускает оценку батча данных агента.

        Args:
            items: Список элементов для оценки.

        Returns:
            Словарь с оценками и сводкой.

        """
        if not items:
            return {"scores": [], "summary": {}}

        dataset_multi, dataset_single = self.prepare_datasets(items)
        logger.info("Running Agent RAGAS evaluation on %d items...", len(items))

        run_config = RunConfig(
            timeout=settings.ragas_timeout,
            max_retries=settings.ragas_max_retries,
            max_wait=max(60, settings.ragas_timeout // 5),
            max_workers=settings.ragas_max_workers,
        )

        scores_list = [{} for _ in items]

        multi_turn_metrics = [
            m
            for m in self.metrics
            if isinstance(m, (AgentGoalAccuracyWithoutReference, ToolCallAccuracy))
        ]
        self._evaluate_part(dataset_multi, multi_turn_metrics, run_config, scores_list, "MultiTurn")

        single_turn_metrics = [
            m
            for m in self.metrics
            if not isinstance(m, (AgentGoalAccuracyWithoutReference, ToolCallAccuracy))
        ]
        self._evaluate_part(
            dataset_single, single_turn_metrics, run_config, scores_list, "SingleTurn"
        )

        summary = self._calculate_summary(scores_list, len(items))

        logger.info("Agent RAGAS Evaluation Complete. Summary: %s", summary)
        return {"scores": scores_list, "summary": summary}
