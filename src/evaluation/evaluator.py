"""Система оценки RAG с использованием RAGAS.

Оркестрирует:
1. Запуск RAG-пайплайна для каждого вопроса
2. Оценку ответов на основе RAGAS
3. Генерацию отчета с метриками
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path

from src.application import RAGService
from src.application.dto import ChatRequest
from src.config.settings import settings
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.evaluation.schemas import (
    EvaluationReport,
    EvaluationResult,
    EvaluationSummary,
    RAGOutput,
    RetrievedContext,
)

logger = logging.getLogger(__name__)


class RAGEvaluator:
    """Оценщик RAG-системы через RAGAS."""

    def __init__(
        self,
        rag_service: RAGService | None = None,
        checkpoint_dir: Path | None = None,
    ) -> None:
        """Инициализирует оценщик.

        Args:
            rag_service: RAG-сервис для генерации ответов.
            checkpoint_dir: Директория для checkpoint'ов.

        """
        self.rag_service = rag_service
        self.ragas = RagasEvaluator()

        if checkpoint_dir:
            self.checkpoint_dir = checkpoint_dir
        else:
            self.checkpoint_dir = settings.project_root / "volumes" / "evaluation"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        self.results: list[EvaluationResult] = []
        self.processed_ids: set[str] = set()

        logger.info("RAGEvaluator инициализирован (RAGAS)")

    def load_dataset(self, path: Path) -> list[dict]:
        """Загружает golden dataset."""
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        logger.info("Загружено %d вопросов из %s", len(data), path)
        return data

    def load_checkpoint(self, checkpoint_file: Path) -> None:
        """Загружает checkpoint."""
        if not checkpoint_file.exists():
            logger.info("Checkpoint не найден, начинаем с нуля")
            return

        with checkpoint_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.results = [EvaluationResult.model_validate(r) for r in data.get("results", [])]
        self.processed_ids = {r.id for r in self.results}
        logger.info("Загружен checkpoint: %d обработанных вопросов", len(self.results))

    def save_checkpoint(self, checkpoint_file: Path) -> None:
        """Сохраняет checkpoint."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "results": [r.model_dump() for r in self.results],
        }
        with checkpoint_file.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    async def run_rag(self, item: dict) -> EvaluationResult:
        """Прогоняет RAG для одного вопроса."""
        result = EvaluationResult(
            id=item.get("id", ""),
            question=item.get("question", ""),
            expected_answer=item.get("expected_answer", ""),
            source_file=item.get("source_file", ""),
            difficulty=item.get("difficulty", ""),
            category=item.get("category", ""),
        )

        if not self.rag_service:
            result.rag_output = RAGOutput(
                generated_answer="[RAG-сервис не подключён]",
                retrieved_contexts=[],
                latency_sec=0,
            )
            return result

        try:
            t0 = time.perf_counter()
            request = ChatRequest(query=result.question, history=[], filters=None)
            response = await self.rag_service.process_query(request)
            rag_latency = time.perf_counter() - t0

            contexts = [
                RetrievedContext(
                    source=src.source_file,
                    content=src.content[:2000],
                    score=src.score,
                )
                for src in response.sources
            ]

            result.rag_output = RAGOutput(
                generated_answer=response.answer,
                rewritten_query=response.rewritten_query or "",
                retrieved_contexts=contexts,
                latency_sec=rag_latency,
                answer_type=response.answer_type,
                timings=response.timings,
            )
        except Exception as e:
            logger.error("Ошибка RAG для %s: %s", result.id, e)
            result.error = f"RAG error: {e}"

        return result

    def _prepare_ragas_items(self, results: list[EvaluationResult]) -> list[dict]:
        """Подготовка элементов для оценки RAGAS."""
        items = []
        for r in results:
            if r.rag_output:
                items.append(
                    {
                        "question": r.question,
                        "expected_answer": r.expected_answer,
                        "generated_answer": r.rag_output.generated_answer,
                        "retrieved_contexts": [
                            {"source": c.source, "content": c.content}
                            for c in r.rag_output.retrieved_contexts
                        ],
                    }
                )
        return items

    def _assign_ragas_scores(
        self, results: list[EvaluationResult], ragas_scores: list[dict]
    ) -> None:
        """Присвоение оценок RAGAS результатам оценки."""
        for i, r in enumerate(results):
            if i < len(ragas_scores):
                scores = ragas_scores[i]
                r.ragas_scores = {
                    "context_recall": scores.get("context_recall", 0),
                    "context_precision": scores.get("context_precision", 0),
                    "faithfulness": scores.get("faithfulness", 0),
                    "answer_relevancy": scores.get("answer_relevancy", 0),
                }
            self.results.append(r)
            self.processed_ids.add(r.id)

    async def evaluate_dataset(
        self,
        dataset: list[dict],
        checkpoint_file: Path | None = None,
        progress_callback=None,
        max_concurrent: int = 1,
    ) -> list[EvaluationResult]:
        """Оценивает весь датасет."""
        if checkpoint_file:
            self.load_checkpoint(checkpoint_file)

        pending = [item for item in dataset if item.get("id") not in self.processed_ids]
        logger.info("К обработке: %d вопросов (уже: %d)", len(pending), len(self.results))

        if not pending:
            return self.results

        semaphore = asyncio.Semaphore(max_concurrent)
        completed = len(self.results)

        async def run_with_limit(item: dict) -> EvaluationResult:
            nonlocal completed
            async with semaphore:
                result = await self.run_rag(item)
            completed += 1
            if progress_callback:
                progress_callback(completed, len(dataset), result)
            return result

        tasks = [run_with_limit(item) for item in pending]
        rag_results = await asyncio.gather(*tasks, return_exceptions=True)

        valid_results = []
        for r in rag_results:
            if isinstance(r, EvaluationResult) and not r.error:
                valid_results.append(r)
            elif isinstance(r, EvaluationResult):
                self.results.append(r)
                self.processed_ids.add(r.id)

        if valid_results:
            logger.info("Запуск RAGAS оценки для %d вопросов...", len(valid_results))
            ragas_items = self._prepare_ragas_items(valid_results)
            ragas_result = await self.ragas.evaluate_batch(ragas_items)
            self._assign_ragas_scores(valid_results, ragas_result["scores"])

        if checkpoint_file:
            self.save_checkpoint(checkpoint_file)

        return self.results

    def generate_report(self) -> EvaluationReport:
        """Генерирует отчёт по результатам."""
        summary = self._compute_summary(self.results)

        by_category = {}
        for cat in {r.category for r in self.results if r.category}:
            by_category[cat] = self._compute_summary([r for r in self.results if r.category == cat])

        by_difficulty = {}
        for diff in {r.difficulty for r in self.results if r.difficulty}:
            by_difficulty[diff] = self._compute_summary(
                [r for r in self.results if r.difficulty == diff]
            )

        metadata = {
            "timestamp": datetime.now().isoformat(),
            "rag_model": settings.eval_rag_model,
            "judge_model": settings.eval_judge_model,
            "evaluator": "RAGAS",
        }

        return EvaluationReport(
            metadata=metadata,
            summary=summary,
            by_category=by_category,
            by_difficulty=by_difficulty,
            results=self.results,
        )

    def _compute_summary(self, results: list[EvaluationResult]) -> EvaluationSummary:
        """Вычисляет сводку по результатам."""
        successful = [r for r in results if r.ragas_scores and not r.error]
        failed = [r for r in results if r.error]

        summary = EvaluationSummary(
            total_questions=len(results),
            successful=len(successful),
            failed=len(failed),
        )

        if successful:
            scores = [r.ragas_scores for r in successful if r.ragas_scores]
            n = len(scores)
            summary.avg_context_recall = sum(s["context_recall"] for s in scores) / n
            summary.avg_context_precision = sum(s["context_precision"] for s in scores) / n
            summary.avg_faithfulness = sum(s["faithfulness"] for s in scores) / n
            summary.avg_answer_relevancy = sum(s["answer_relevancy"] for s in scores) / n

            rag_latencies = [r.rag_output.latency_sec for r in successful if r.rag_output]
            if rag_latencies:
                summary.avg_rag_latency_sec = sum(rag_latencies) / len(rag_latencies)

            timings_list = [
                r.rag_output.timings for r in successful if r.rag_output and r.rag_output.timings
            ]
            if timings_list:
                n_timings = len(timings_list)
                summary.avg_query_expansion_sec = (
                    sum(t.get("query_expansion", 0) for t in timings_list) / n_timings
                )
                summary.avg_retrieve_sec = (
                    sum(t.get("retrieve", 0) for t in timings_list) / n_timings
                )
                summary.avg_rerank_sec = sum(t.get("rerank", 0) for t in timings_list) / n_timings
                summary.avg_llm_analysis_sec = (
                    sum(t.get("llm_analysis", 0) for t in timings_list) / n_timings
                )
                summary.avg_llm_generation_sec = (
                    sum(t.get("llm_generation", 0) for t in timings_list) / n_timings
                )

        return summary
