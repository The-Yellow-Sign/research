"""CLI для запуска оценки RAG-системы с RAGAS.

Использование:
    uv run python -m src.evaluation.run_evaluation --sample 5
    uv run python -m src.evaluation.run_evaluation --resume
"""

import argparse
import asyncio
import json
import logging
import math
import os
import sys

os.environ["TOKENIZERS_PARALLELISM"] = "false"

from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from src.application import RAGService
from src.evaluation.eval_llm_client import EvalLLMClient
from src.evaluation.evaluator import RAGEvaluator
from src.evaluation.schemas import (
    EvaluationReport,
)
from src.infrastructure.search import SearchEngine

console = Console()


def setup_logging(verbose: bool = False) -> None:
    """Настраивает логирование."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )


def display_summary(report: EvaluationReport) -> None:
    """Отображает сводку в консоли."""
    console.print("\n")
    console.print("[bold cyan]Результаты оценки RAG (RAGAS)[/bold cyan]")
    console.print()

    s = report.summary
    table = Table(title="Общая сводка")
    table.add_column("Метрика", style="cyan")
    table.add_column("Значение", style="green")

    table.add_row("Всего вопросов", str(s.total_questions))
    table.add_row("Успешно", str(s.successful))
    table.add_row("Ошибок", str(s.failed))
    table.add_row("", "")

    def fmt_pct(val: float) -> str:
        """Форматирует проценты, обрабатывая NaN."""
        if math.isnan(val):
            return "N/A"
        return f"{val * 100:.1f}%"

    table.add_row("Context Recall", fmt_pct(s.avg_context_recall))
    table.add_row("Context Precision", fmt_pct(s.avg_context_precision))
    table.add_row("Faithfulness", fmt_pct(s.avg_faithfulness))
    table.add_row("Answer Relevancy", fmt_pct(s.avg_answer_relevancy))
    table.add_row("", "")
    table.add_row("Avg RAG latency", f"{s.avg_rag_latency_sec:.2f}s")

    console.print(table)

    if report.by_category:
        cat_table = Table(title="По категориям")
        cat_table.add_column("Категория", style="cyan")
        cat_table.add_column("N", style="dim")
        cat_table.add_column("Recall", style="green")
        cat_table.add_column("Precision", style="green")
        cat_table.add_column("Faith.", style="green")
        cat_table.add_column("Relevancy", style="green")

        for cat, summary in report.by_category.items():
            cat_table.add_row(
                cat,
                str(summary.total_questions),
                f"{summary.avg_context_recall * 100:.0f}",
                f"{summary.avg_context_precision * 100:.0f}",
                f"{summary.avg_faithfulness * 100:.0f}",
                f"{summary.avg_answer_relevancy * 100:.0f}",
            )
        console.print(cat_table)

    if report.by_difficulty:
        diff_table = Table(title="По сложности")
        diff_table.add_column("Сложность", style="cyan")
        diff_table.add_column("N", style="dim")
        diff_table.add_column("Recall", style="green")
        diff_table.add_column("Precision", style="green")
        diff_table.add_column("Faith.", style="green")
        diff_table.add_column("Relevancy", style="green")

        for diff, summary in report.by_difficulty.items():
            diff_table.add_row(
                diff,
                str(summary.total_questions),
                f"{summary.avg_context_recall * 100:.0f}",
                f"{summary.avg_context_precision * 100:.0f}",
                f"{summary.avg_faithfulness * 100:.0f}",
                f"{summary.avg_answer_relevancy * 100:.0f}",
            )
        console.print(diff_table)


def save_report(report: EvaluationReport, output_dir: Path) -> tuple[Path, Path]:
    """Сохраняет отчёт в JSON и Markdown."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    json_path = output_dir / f"evaluation_{timestamp}.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, ensure_ascii=False, indent=2)

    md_path = output_dir / f"evaluation_{timestamp}.md"
    md_content = generate_markdown_report(report)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(md_content)

    return json_path, md_path


def generate_markdown_report(report: EvaluationReport) -> str:
    """Генерирует Markdown-отчёт."""
    s = report.summary
    lines = [
        "# RAG Evaluation Report (RAGAS)",
        "",
        f"**Дата:** {report.metadata.get('timestamp', 'N/A')}",
        f"**RAG Model:** {report.metadata.get('rag_model', 'N/A')}",
        f"**Evaluator:** {report.metadata.get('evaluator', 'RAGAS')}",
        "",
        "## Общая сводка",
        "",
        "| Метрика | Значение |",
        "|---------|----------|",
        f"| Всего вопросов | {s.total_questions} |",
        f"| Успешно | {s.successful} |",
        f"| Ошибок | {s.failed} |",
        f"| **Context Recall** | {s.avg_context_recall * 100:.1f}% |",
        f"| **Context Precision** | {s.avg_context_precision * 100:.1f}% |",
        f"| **Faithfulness** | {s.avg_faithfulness * 100:.1f}% |",
        f"| **Answer Relevancy** | {s.avg_answer_relevancy * 100:.1f}% |",
        f"| Avg RAG latency | {s.avg_rag_latency_sec:.2f}s |",
        "",
    ]

    if report.by_category:
        lines.append("## По категориям")
        lines.append("")
        lines.append("| Категория | N | Recall | Precision | Faith. | Relevancy |")
        lines.append("|-----------|---|--------|-----------|--------|-----------|")
        for cat, summary in report.by_category.items():
            r = summary.avg_context_recall * 100
            p = summary.avg_context_precision * 100
            f = summary.avg_faithfulness * 100
            a = summary.avg_answer_relevancy * 100
            lines.append(
                f"| {cat} | {summary.total_questions} | {r:.0f} | {p:.0f} | {f:.0f} | {a:.0f} |"
            )
        lines.append("")

    if report.by_difficulty:
        lines.append("## По сложности")
        lines.append("")
        lines.append("| Сложность | N | Recall | Precision | Faith. | Relevancy |")
        lines.append("|-----------|---|--------|-----------|--------|-----------|")
        for diff, summary in report.by_difficulty.items():
            r = summary.avg_context_recall * 100
            p = summary.avg_context_precision * 100
            f = summary.avg_faithfulness * 100
            a = summary.avg_answer_relevancy * 100
            lines.append(
                f"| {diff} | {summary.total_questions} | {r:.0f} | {p:.0f} | {f:.0f} | {a:.0f} |"
            )
        lines.append("")

    return "\n".join(lines)


def _init_rag_service(args) -> "RAGService | None":
    """Инициализирует RAG Service."""
    if args.skip_rag:
        return None
    try:
        console.print("Загрузка SearchEngine...")
        search_engine = SearchEngine()
        console.print("Инициализация OpenRouter LLM для RAG...")
        console.print("Инициализация OpenRouter LLM для RAG...")

        eval_llm_client = EvalLLMClient()
        rag_service = RAGService(search_engine=search_engine, llm_client=eval_llm_client)
        console.print(f"  [green]RAG Service готов (model: {eval_llm_client.model})[/green]")
        return rag_service
    except Exception as e:
        console.print(f"  [yellow]RAG Service недоступен: {e}[/yellow]")
        console.print("  Используйте --skip-rag для работы без RAG")
        sys.exit(1)


def _filter_dataset(dataset: list[dict], args) -> list[dict]:
    """Применяет фильтры к датасету."""
    if args.sample:
        dataset = dataset[: args.sample]
        console.print(f"[dim]Ограничено до {args.sample} вопросов[/dim]")
    if args.category:
        dataset = [d for d in dataset if d.get("category") == args.category]
        console.print(f"[dim]Фильтр: {args.category} ({len(dataset)} вопросов)[/dim]")
    if args.difficulty:
        dataset = [d for d in dataset if d.get("difficulty") == args.difficulty]
        console.print(f"[dim]Сложность: {args.difficulty} ({len(dataset)} вопросов)[/dim]")
    return dataset


async def run_evaluation(args: argparse.Namespace) -> None:
    """Основная функция запуска оценки."""
    dataset_path = Path(args.dataset)
    if not dataset_path.exists():
        console.print(f"[red]Файл не найден: {dataset_path}[/red]")
        sys.exit(1)

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_file = output_dir / "checkpoint.json" if args.resume else None

    console.print("[bold]Инициализация...[/bold]")
    rag_service = _init_rag_service(args)

    evaluator = RAGEvaluator(
        rag_service=rag_service,
        checkpoint_dir=output_dir,
    )

    dataset = evaluator.load_dataset(dataset_path)
    dataset = _filter_dataset(dataset, args)
    console.print(f"\n[bold]К обработке: {len(dataset)} вопросов[/bold]\n")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task("Оценка", total=len(dataset))

        def progress_callback(done: int, total: int, result) -> None:
            progress.update(task_id, completed=done)

        try:
            max_concurrent = 1 if rag_service else 10
            await evaluator.evaluate_dataset(
                dataset=dataset,
                checkpoint_file=checkpoint_file,
                progress_callback=progress_callback,
                max_concurrent=max_concurrent,
            )
        except KeyboardInterrupt:
            console.print("\n[yellow]Прервано пользователем. Сохраняем результаты...[/yellow]")

    report = evaluator.generate_report()
    display_summary(report)

    json_path, md_path = save_report(report, output_dir)
    console.print("\n[green]✓ Отчёт сохранён:[/green]")
    console.print(f"  JSON: {json_path}")
    console.print(f"  MD: {md_path}")


def main() -> None:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(description="Оценка RAG-системы через RAGAS")

    parser.add_argument(
        "--dataset",
        type=str,
        default="tests/data/golden_dataset.json",
        help="Путь к golden dataset",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="volumes/evaluation",
        help="Директория для результатов",
    )
    parser.add_argument(
        "--sample",
        type=int,
        help="Ограничить количество вопросов",
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Фильтр по категории",
    )
    parser.add_argument(
        "--difficulty",
        type=str,
        help="Фильтр по сложности (simple/medium/hard)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Продолжить с checkpoint",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Пропустить прогон RAG (для тестирования)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Подробный вывод",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    asyncio.run(run_evaluation(args))


if __name__ == "__main__":
    main()
