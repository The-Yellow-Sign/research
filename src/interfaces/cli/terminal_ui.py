"""Терминальный UI для RAG-чатбота.

Тонкий презентационный слой на Rich и PromptToolkit.
Вся бизнес-логика делегирована RAGService.
"""

import asyncio
import logging

from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from src.application import RAGService
from src.application.dto import ChatRequest, ChatResponse
from src.config.logging_config import setup_logging
from src.domain.models import SourceDoc
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.search import SearchEngine

logger = logging.getLogger(__name__)


class TerminalUI:
    """Терминальный презентационный слой для RAG-чатбота."""

    def __init__(self) -> None:
        """Инициализация терминального UI с сервисом и консолью."""
        self.console = Console(force_terminal=True)
        self.console.print("[dim]🔧 Загрузка моделей...[/dim]")

        search_engine = SearchEngine()
        llm_client = LLMClient()
        self.service = RAGService(llm_client=llm_client, search_engine=search_engine)

        self.history: list[dict[str, str]] = []
        self.session = self._create_prompt_session()

    def _create_prompt_session(self) -> PromptSession:
        """Создаёт PromptToolkit-сессию с поддержкой многострочного ввода."""
        bindings = KeyBindings()

        @bindings.add("escape", "enter")
        def _(event):
            event.current_buffer.insert_text("\n")

        return PromptSession(multiline=False, key_bindings=bindings)

    def _print_footnotes(self, footnotes: list | None) -> None:
        """Выводит footnotes с разделением на 📄 Docs и 🌐 Web."""
        if not footnotes:
            return

        doc_footnotes = [f for f in footnotes if f.source_type == "doc"]
        web_footnotes = [f for f in footnotes if f.source_type == "web"]

        if doc_footnotes:
            self.console.print("\n[bold cyan]📄 Документы:[/bold cyan]")
            for fn in doc_footnotes:
                service_tag = f" ({fn.service})" if fn.service else ""
                self.console.print(
                    f"  [dim][{fn.id}][/dim] [yellow]{fn.title}{service_tag}[/yellow]"
                )
                if fn.header_path:
                    self.console.print(f"      [dim]↳ {fn.header_path}[/dim]")

        if web_footnotes:
            self.console.print("\n[bold magenta]🌐 Веб-источники:[/bold magenta]")
            for fn in web_footnotes:
                self.console.print(f"  [dim][{fn.id}][/dim] [blue]{fn.title}[/blue]")
                if fn.url:
                    self.console.print(f"      [dim]↳ {fn.url}[/dim]")
                if fn.quote:
                    quote_preview = fn.quote[:150] + "..." if len(fn.quote) > 150 else fn.quote
                    self.console.print(f'      [dim]"{quote_preview}"[/dim]')

    def _print_sources_table(self, sources: list[SourceDoc]) -> None:
        """Выводит таблицу с ранжированными источниками (fallback)."""
        if not sources:
            return

        table = Table(
            title="📚 Использованные источники (Reranked)",
            box=box.ROUNDED,
            show_lines=True,
        )
        table.add_column("№", style="dim", width=3)
        table.add_column("Score", justify="right", width=8)
        table.add_column("Service", style="cyan", width=12)
        table.add_column("Context Path", style="yellow")

        for source in sources:
            score_style = "green" if source.score > 0.5 else "red"
            context_path = (
                f"{source.source_file}\n↳ {source.header_path}"
                if source.header_path
                else source.source_file
            )
            table.add_row(
                str(source.rank),
                f"[{score_style}]{source.score:.4f}[/{score_style}]",
                source.service,
                context_path,
            )

        self.console.print(table)

    def _render_response(self, response: ChatResponse) -> None:
        """Рендерит ChatResponse в терминал."""
        if response.answer_type == "clarifying_question":
            self.console.print(
                Panel(
                    Markdown(response.answer),
                    title="🤖 Уточнение",
                    border_style="yellow",
                )
            )
        else:
            self.console.print(
                Panel(
                    Markdown(response.answer),
                    title="🤖 Ответ",
                    border_style="green",
                )
            )
            if response.footnotes:
                self._print_footnotes(response.footnotes)
            else:
                self._print_sources_table(response.sources)

    def _handle_command(self, command: str) -> bool:
        """Обрабатывает специальные команды."""
        cmd = command.strip().lower()

        if cmd in ("/quit", "/exit", "/q", "q", "exit", "quit"):
            self.console.print("[dim]👋 До свидания![/dim]")
            return True

        if cmd in ("/clear", "/c"):
            self.history.clear()
            self.console.clear()
            self.console.print("[dim]🧹 История очищена[/dim]")
            return True

        if cmd == "/help":
            self.console.print(
                Panel(
                    "[bold]/clear[/bold] - очистить историю\n"
                    "[bold]/quit[/bold] - выйти\n"
                    "[bold]/help[/bold] - эта справка\n\n"
                    "[dim]Esc+Enter - новая строка[/dim]",
                    title="📖 Команды",
                    border_style="blue",
                )
            )
            return True

        return False

    async def run(self) -> None:
        """Запускает асинхронный интерактивный цикл чата."""
        self.console.print(
            Panel(
                "🚀 RAG Bot\n[dim]Введите вопрос или /help для справки[/dim]",
                style="bold blue",
            )
        )

        while True:
            try:
                user_input = await self.session.prompt_async("\n👤 Вы: ")

                if not user_input.strip():
                    continue

                if user_input.startswith("/") or user_input.lower() in ("q", "exit", "quit"):
                    if self._handle_command(user_input):
                        if user_input.lower() in ("q", "exit", "quit", "/quit", "/exit", "/q"):
                            break
                        continue

                request = ChatRequest(query=user_input, history=self.history)
                self.console.print("[grey50]🔄 Обработка запроса...[/grey50]")

                response = await self.service.process_query(request)

                if response.rewritten_query != user_input:
                    self.console.print(f"[grey50]🔄 Rewriter: {response.rewritten_query}[/grey50]")

                self._render_response(response)

                if response.answer_type == "final_answer":
                    self.history.append({"role": "user", "content": user_input})
                    self.history.append({"role": "assistant", "content": response.answer})

            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[dim]👋 До свидания![/dim]")
                break
            except Exception as e:
                self.console.print(f"[bold red]❌ Ошибка:[/bold red] {e}")
                logger.exception("Ошибка обработки запроса")


def main() -> None:
    """Запускает терминальный UI в асинхронном режиме."""
    setup_logging(level=logging.INFO)
    ui = TerminalUI()
    try:
        asyncio.run(ui.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
