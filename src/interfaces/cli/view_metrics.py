"""CLI-утилита для просмотра собранных метрик RAG-пайплайна.

Запуск:
    uv run python -m src.interfaces.cli.view_metrics

Опции:
    --last N     Показать последние N записей из буфера (по умолчанию 100)
    --file PATH  Показать метрики из указанного JSONL-файла
    --summary    Показать только сводку
"""

import argparse
import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.config.metrics import METRICS_DIR, get_metrics_collector

console = Console()


def display_summary(summary: dict) -> None:
    """Отображает сводку метрик в красивом формате."""
    console.print()
    console.print(Panel.fit("[bold cyan]📊 Сводка метрик RAG-пайплайна[/bold cyan]"))


    llm = summary.get("llm", {})
    llm_table = Table(title="🤖 LLM-вызовы", show_header=True, header_style="bold magenta")
    llm_table.add_column("Метрика", style="cyan")
    llm_table.add_column("Значение", style="green")

    llm_table.add_row("Количество вызовов", str(llm.get("count", 0)))
    llm_table.add_row("Avg latency (sec)", f"{llm.get('avg_duration_sec', 0):.3f}")
    llm_table.add_row("Total tokens IN", str(llm.get("total_tokens_in", 0)))
    llm_table.add_row("Total tokens OUT", str(llm.get("total_tokens_out", 0)))
    llm_table.add_row("Error rate", f"{llm.get('error_rate', 0):.1%}")

    console.print(llm_table)


    search = summary.get("search", {})
    search_table = Table(title="🔍 Поисковые операции", show_header=True, header_style="bold blue")
    search_table.add_column("Метрика", style="cyan")
    search_table.add_column("Значение", style="green")

    search_table.add_row("Количество запросов", str(search.get("count", 0)))
    search_table.add_row("Avg latency (sec)", f"{search.get('avg_duration_sec', 0):.3f}")
    search_table.add_row("Avg hits", f"{search.get('avg_hits', 0):.1f}")

    console.print(search_table)


    requests = summary.get("requests", {})
    req_table = Table(title="📨 Обработанные запросы", show_header=True, header_style="bold yellow")
    req_table.add_column("Метрика", style="cyan")
    req_table.add_column("Значение", style="green")

    req_table.add_row("Всего запросов", str(requests.get("count", 0)))
    req_table.add_row("Avg total latency (sec)", f"{requests.get('avg_duration_sec', 0):.3f}")

    by_type = requests.get("by_answer_type", {})
    req_table.add_row("Final answers", str(by_type.get("final_answer", 0)))
    req_table.add_row("Clarifying questions", str(by_type.get("clarifying_question", 0)))

    console.print(req_table)
    console.print()


def load_metrics_from_file(filepath: Path) -> list[dict]:
    """Загружает метрики из JSONL-файла."""
    if not filepath.exists():
        console.print(f"[red]Файл не найден: {filepath}[/red]")
        return []

    records = []
    with filepath.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return records


def display_records(records: list[dict], limit: int = 20) -> None:
    """Отображает последние записи метрик."""
    if not records:
        console.print("[yellow]Нет записей для отображения[/yellow]")
        return

    table = Table(title=f"📋 Последние {min(limit, len(records))} записей")
    table.add_column("Время", style="dim")
    table.add_column("Тип", style="cyan")
    table.add_column("Детали", style="green")

    for record in records[-limit:]:
        ts = record.get("timestamp", "")[:19]
        rtype = record.get("type", "?")

        if rtype == "llm_call":
            details = f"{record.get('operation', '?')} | {record.get('duration_sec', 0):.2f}s"
        elif rtype == "search":
            details = f"{record.get('engine', '?')} | {record.get('hits_count', 0)} hits"
        elif rtype == "pipeline_stage":
            details = f"{record.get('stage', '?')} | {record.get('duration_sec', 0):.2f}s"
        elif rtype == "request":
            dur = record.get("total_duration_sec", 0)
            details = f"{record.get('answer_type', '?')} | {dur:.2f}s"
        else:
            details = str(record)[:50]

        table.add_row(ts, rtype, details)

    console.print(table)


def main() -> None:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(description="Просмотр метрик RAG-пайплайна")
    parser.add_argument("--last", type=int, default=100, help="Количество последних записей")
    parser.add_argument("--file", type=str, help="Путь к JSONL-файлу с метриками")
    parser.add_argument("--summary", action="store_true", help="Показать только сводку")
    args = parser.parse_args()

    console.print("[bold]🔭 RAG Metrics Viewer[/bold]")

    if args.file:
        filepath = Path(args.file)
        records = load_metrics_from_file(filepath)
        console.print(f"Загружено {len(records)} записей из {filepath}")

        if not args.summary:
            display_records(records, args.last)
    else:

        collector = get_metrics_collector()
        summary = collector.get_summary(args.last)
        display_summary(summary)

        if not args.summary:
            console.print(f"\n[dim]Размер буфера: {collector.get_buffer_size()}[/dim]")
            console.print(f"[dim]Директория метрик: {METRICS_DIR}[/dim]")


            if METRICS_DIR.exists():
                files = sorted(METRICS_DIR.glob("metrics_*.jsonl"))
                if files:
                    names = ", ".join(f.name for f in files[-5:])
                    console.print(f"[dim]Доступные файлы: {names}[/dim]")


if __name__ == "__main__":
    main()
