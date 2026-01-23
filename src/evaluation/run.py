"""Unified Evaluation Runner (Agent + RAG).

Этот модуль объединяет запуск оценки для RAG и Agent-систем.
Поддерживает checkpointing, RAGAS-оценку и генерацию отчетов.

Usage:
    python -m src.evaluation.run --mode agent --dataset rag_test_dataset.json --output report.json
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from src.application.services.rag_service import RAGService
from src.application.services.tool_factory import create_default_tools
from src.application.use_cases.agent_controller import AgentController
from src.evaluation.adapters import AgentAdapter, BaseSystemAdapter, RAGAdapter
from src.evaluation.agent_ragas_evaluator import AgentRagasEvaluator
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.evaluation.schemas import (
    EvaluationReport,
    EvaluationResult,
    EvaluationSummary,
)
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.search.engine import SearchEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)],
)
logger = logging.getLogger("eval_runner")
console = Console()


class UnifiedEvaluator:
    """Универсальный класс для оценки RAG и Agent систем."""

    def __init__(
        self,
        adapter: BaseSystemAdapter,
        output_dir: Path,
        resume: bool = False,
        ragas_enabled: bool = True,
    ):
        self.adapter = adapter
        self.output_dir = output_dir
        self.resume = resume
        self.ragas_enabled = ragas_enabled

        self.results: list[EvaluationResult] = []
        self.processed_ids: set[str] = set()
        self.checkpoint_file = self.output_dir / "checkpoint.json"

        if not self.output_dir.exists():
            self.output_dir.mkdir(parents=True)

        self._load_checkpoint()

    def _load_checkpoint(self) -> None:
        """Загружает состояние из чекпоинта, если требуется."""
        if self.resume and self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, encoding="utf-8") as f:
                    data = json.load(f)
                    self.results = [EvaluationResult(**item) for item in data]
                    self.processed_ids = {r.id for r in self.results}
                logger.info(
                    "Resumed from checkpoint. Loaded %d processed items.",
                    len(self.results),
                )
            except Exception as e:
                logger.error("Failed to load checkpoint: %s. Starting fresh.", e)

    def _save_checkpoint(self) -> None:
        """Сохраняет текущие результаты в чекпоинт."""
        try:
            data = [r.model_dump() for r in self.results]
            with open(self.checkpoint_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Failed to save checkpoint: %s", e)

    async def evaluate_dataset(
        self,
        dataset_path: Path,
        sample_size: int | None = None,
    ) -> None:
        """Запускает цикл оценки по датасету."""
        with open(dataset_path, encoding="utf-8") as f:
            dataset = json.load(f)

        pending_items = [item for item in dataset if str(item.get("id")) not in self.processed_ids]

        if sample_size:
            pending_items = pending_items[:sample_size]
            logger.info("Sampling %d items from dataset.", sample_size)

        if not pending_items:
            logger.info("No items to process. Evaluation already complete?")
        else:
            logger.info("Starting evaluation of %d items...", len(pending_items))

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Evaluating...", total=len(pending_items))

            for item in pending_items:
                q_id = str(item.get("id"))
                question = item.get("question")
                expected = item.get("ground_truth") or item.get("expected_answer")

                expected_val = expected
                if isinstance(expected, list) and len(expected) == 1:
                    expected_val = str(expected[0])
                elif isinstance(expected, list):
                    expected_val = [str(e) for e in expected]
                else:
                    expected_val = str(expected)

                try:
                    rag_output = await self.adapter.run(question)

                    result = EvaluationResult(
                        id=q_id,
                        question=question,
                        expected_answer=expected_val,
                        source_file=item.get("source_file", ""),
                        difficulty=item.get("difficulty", ""),
                        category=item.get("category", ""),
                        rag_output=rag_output,
                        keywords=item.get("expected_answer_contains") or item.get("keywords", []),
                        meta=item.get("meta", {}),
                    )

                except Exception as e:
                    logger.exception("Error processing item %s", q_id)
                    result = EvaluationResult(
                        id=q_id, question=question, expected_answer=expected_val, error=str(e)
                    )

                self.results.append(result)
                self.processed_ids.add(q_id)
                self._save_checkpoint()
                progress.advance(task)

        if self.ragas_enabled:
            await self._run_ragas_evaluation()

        self._generate_final_report()

    async def _run_ragas_evaluation(self) -> None:
        """Запускает RAGAS оценку на собранных результатах."""
        logger.info("Starting RAGAS evaluation phase...")

        if isinstance(self.adapter, AgentAdapter):
            evaluator = AgentRagasEvaluator()
        else:
            evaluator = RagasEvaluator()

        ragas_input = self._prepare_ragas_inputs()

        if not ragas_input:
            logger.warning("No valid results for RAGAS evaluation.")
            return

        scores_result = await evaluator.evaluate_batch(ragas_input)
        scores_list = scores_result.get("scores", [])

        valid_indices = [i for i, r in enumerate(self.results) if not r.error and r.rag_output]

        for idx, score_dict in zip(valid_indices, scores_list, strict=False):
            if score_dict:
                self.results[idx].ragas_scores = score_dict
                if self.results[idx].rag_output:
                    self.results[idx].rag_output.ragas_scores = score_dict

        self._save_checkpoint()

    def _prepare_ragas_inputs(self) -> list[dict]:
        """Подготавливает данные для оценки в RAGAS."""
        ragas_input = []
        for r in self.results:
            if r.error or not r.rag_output:
                continue

            ctxs = []
            if r.rag_output.retrieved_contexts:
                ctxs = [c.model_dump() for c in r.rag_output.retrieved_contexts]

            tool_calls = []
            if r.rag_output and r.rag_output.trace:
                for step in r.rag_output.trace:
                    if step.action:
                        tool_calls.append(
                            {"name": step.action, "args": step.params, "result": step.observation}
                        )

            expected_tools = []
            if r.meta:
                expected_tools = r.meta.get("expected_tools", [])

            ragas_input.append(
                {
                    "question": r.question,
                    "generated_answer": r.rag_output.generated_answer,
                    "expected_answer": r.expected_answer,
                    "retrieved_contexts": ctxs,
                    "tool_calls": tool_calls,
                    "expected_tools": expected_tools,
                    "trace": (
                        [t.model_dump() for t in r.rag_output.trace] if r.rag_output.trace else []
                    ),
                }
            )
        return ragas_input

    def _generate_final_report(self) -> None:
        """Генерирует финальный JSON отчет и сводку."""
        output_file = self.output_dir / "final_report.json"

        total = len(self.results)
        success = len([r for r in self.results if not r.error])
        failed = total - success

        ragas_keys = [
            "context_recall",
            "context_precision",
            "faithfulness",
            "answer_relevancy",
            "agent_goal_accuracy",
        ]
        sums = dict.fromkeys(ragas_keys, 0.0)
        count_with_scores = 0

        latencies = []

        timings_accumulator = {
            "query_expansion_sec": [],
            "retrieve_sec": [],
            "rerank_sec": [],
            "llm_analysis_sec": [],
            "llm_generation_sec": [],
        }

        for r in self.results:
            if r.rag_output:
                latencies.append(r.rag_output.latency_sec)

                if r.rag_output.timings:
                    for key in timings_accumulator:
                        val = r.rag_output.timings.get(key)
                        if val is not None:
                            timings_accumulator[key].append(val)

                if r.ragas_scores:
                    count_with_scores += 1
                    for k in ragas_keys:
                        sums[k] += r.ragas_scores.get(k, 0.0)

        def calc_avg(values: list[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        summary = EvaluationSummary(
            total_questions=total,
            successful=success,
            failed=failed,
            avg_rag_latency_sec=calc_avg(latencies),
            avg_context_recall=(
                sums["context_recall"] / count_with_scores if count_with_scores else 0.0
            ),
            avg_context_precision=(
                sums["context_precision"] / count_with_scores if count_with_scores else 0.0
            ),
            avg_faithfulness=(
                sums["faithfulness"] / count_with_scores if count_with_scores else 0.0
            ),
            avg_answer_relevancy=(
                sums["answer_relevancy"] / count_with_scores if count_with_scores else 0.0
            ),
            avg_query_expansion_sec=calc_avg(timings_accumulator["query_expansion_sec"]),
            avg_retrieve_sec=calc_avg(timings_accumulator["retrieve_sec"]),
            avg_rerank_sec=calc_avg(timings_accumulator["rerank_sec"]),
            avg_llm_analysis_sec=calc_avg(timings_accumulator["llm_analysis_sec"]),
            avg_llm_generation_sec=calc_avg(timings_accumulator["llm_generation_sec"]),
        )

        report = EvaluationReport(
            metadata={
                "timestamp": datetime.now().isoformat(),
                "mode": "agent" if isinstance(self.adapter, AgentAdapter) else "rag",
            },
            summary=summary,
            results=self.results,
        )

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(exclude_none=True, indent=2))

        logger.info("Final report saved to %s", output_file)

        console.print("\n[bold green]Evaluation Complete![/bold green]")
        console.print(f"Total: {total}, Success: {success}, Failed: {failed}")
        console.print(f"Avg Latency: {summary.avg_rag_latency_sec:.2f}s")
        if count_with_scores:
            console.print("[bold]RAGAS Scores:[/bold]")
            console.print(f"  Recall: {summary.avg_context_recall:.3f}")
            console.print(f"  Precision: {summary.avg_context_precision:.3f}")
            console.print(f"  Faithfulness: {summary.avg_faithfulness:.3f}")


async def main():
    """Точка входа для unified evaluation runner."""
    parser = argparse.ArgumentParser(description="Unified Evaluation Runner")
    parser.add_argument(
        "--mode", choices=["rag", "agent", "both"], required=True, help="Evaluation mode"
    )
    parser.add_argument("--dataset", type=Path, required=True, help="Path to test dataset")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("evaluation_results"),
        help="Directory for results",
    )
    parser.add_argument("--sample", type=int, help="Number of items to sample")
    parser.add_argument("--ragas", action="store_true", help="Enable RAGAS evaluation")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")

    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir / f"{args.mode}_{timestamp}"

    llm_client = LLMClient()
    search_engine = SearchEngine()
    rag_service = RAGService(llm_client, search_engine)

    tools = create_default_tools(search_engine=search_engine, llm_client=llm_client)

    agent_controller = AgentController(llm=llm_client, tools=tools)

    adapters = []
    if args.mode == "rag":
        adapters.append(("rag", RAGAdapter(rag_service)))
    elif args.mode == "agent":
        adapters.append(("agent", AgentAdapter(agent_controller)))
    elif args.mode == "both":
        adapters.append(("rag", RAGAdapter(rag_service)))
        adapters.append(("agent", AgentAdapter(agent_controller)))

    for name, adapter in adapters:
        logger.info(f"Starting evaluation for {name}...")
        mode_output_dir = output_dir / name

        evaluator = UnifiedEvaluator(
            adapter=adapter,
            output_dir=mode_output_dir,
            resume=args.resume,
            ragas_enabled=args.ragas,
        )

        await evaluator.evaluate_dataset(dataset_path=args.dataset, sample_size=args.sample)


if __name__ == "__main__":
    asyncio.run(main())
