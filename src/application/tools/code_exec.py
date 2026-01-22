"""Инструмент выполнения Python-кода в песочнице.

Безопасное выполнение кода с ограничениями по времени и модулям.
"""

import ast
import asyncio
import builtins
import logging
import sys
from io import StringIO
from typing import Any

from src.application.tools.tool_base import (
    BaseTool,
    ToolParameter,
    ToolParameterType,
    ToolResult,
)
from src.config import settings

logger = logging.getLogger(__name__)


ALLOWED_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

ALLOWED_MODULES = {"json", "re", "math", "datetime", "collections", "itertools", "time"}

CODE_EXEC_DESCRIPTION = (
    "Выполняет Python-код в песочнице. Используй для вычислений, парсинга данных, форматирования."
)

CODE_PARAM_DESCRIPTION = (
    "Python-код для выполнения. "
    "Результат должен быть в переменной 'result' или выведен через print()."
)


class RestrictedImportError(Exception):
    """Ошибки при попытке импорта запрещенного модуля."""

    pass


def _safe_import(name: str, *args: Any, **kwargs: Any) -> Any:
    """Безопасный импорт, разрешающий только модули из белого списка."""
    if name not in ALLOWED_MODULES:
        msg = f"Импорт модуля '{name}' запрещён. Разрешены: {ALLOWED_MODULES}"
        raise RestrictedImportError(msg)
    return builtins.__import__(name, *args, **kwargs)


def _validate_imports(tree: ast.AST) -> str | None:
    """Проверяет, что все импорты разрешены.

    Returns:
        Сообщение об ошибке или None если всё ок.

    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            module_name = node.names[0].name if isinstance(node, ast.Import) else node.module or ""
            base_module = module_name.split(".")[0]
            if base_module not in ALLOWED_MODULES:
                return f"Импорт '{base_module}' запрещён."
    return None


def _build_restricted_globals() -> dict[str, Any]:
    """Создаёт ограниченное глобальное окружение."""
    restricted_globals: dict[str, Any] = {
        "__builtins__": {**ALLOWED_BUILTINS, "__import__": _safe_import},
    }

    for module_name in ALLOWED_MODULES:
        try:
            restricted_globals[module_name] = __import__(module_name)
        except ImportError:
            pass

    return restricted_globals


def _format_output(
    output: str,
    local_vars: dict[str, Any],
    max_len: int,
) -> str:
    """Форматирует вывод выполнения кода."""
    if "result" in local_vars:
        result_value = str(local_vars["result"])
        if output:
            output = f"{output}\nresult = {result_value}"
        else:
            output = result_value

    if not output:
        output = (
            "Код выполнен успешно, но ничего не выведено. "
            "Используй print() или переменную 'result'."
        )

    if len(output) > max_len:
        output = output[:max_len] + "\n... (обрезано)"

    return output


class CodeExecTool(BaseTool):
    """Выполнение Python-кода в изолированной среде."""

    name = "code_exec"
    description = CODE_EXEC_DESCRIPTION
    parameters = [
        ToolParameter(
            name="code",
            type=ToolParameterType.STRING,
            description=CODE_PARAM_DESCRIPTION,
            required=True,
        ),
    ]

    TIMEOUT_SEC = 5
    MAX_OUTPUT_LEN = settings.code_exec_max_output

    async def execute(self, code: str, **kwargs: Any) -> ToolResult:
        """Выполняет код в песочнице.

        Args:
            code: Python-код для выполнения.
            **kwargs: Дополнительные параметры (игнорируются).

        Returns:
            ToolResult с результатом выполнения или ошибкой.

        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return ToolResult(
                success=False,
                data="",
                error=f"Синтаксическая ошибка: {e}",
            )

        import_error = _validate_imports(tree)
        if import_error:
            return ToolResult(success=False, data="", error=import_error)

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._run_code_sync, tree),
                timeout=self.TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            return ToolResult(
                success=False,
                data="",
                error=f"Превышен лимит времени ({self.TIMEOUT_SEC}с). Упростите код.",
            )
        except Exception as e:
            logger.error("code_exec unexpected error: %s", e)
            return ToolResult(success=False, data="", error=str(e))

    def _run_code_sync(self, tree: ast.AST) -> ToolResult:
        """Выполняет предварительно проверенный код в синхронном режиме."""
        restricted_globals = _build_restricted_globals()
        local_vars: dict[str, Any] = {}

        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            exec(  # noqa: S102
                compile(tree, "<sandbox>", "exec"),
                restricted_globals,
                local_vars,
            )

            output = captured_output.getvalue()
            output = _format_output(output, local_vars, self.MAX_OUTPUT_LEN)

            logger.info(
                "code_exec: успешно выполнен код (%d символов вывода)",
                len(output),
            )

            return ToolResult(success=True, data=output)

        except RestrictedImportError as e:
            return ToolResult(success=False, data="", error=str(e))
        except Exception as e:
            logger.warning("code_exec error: %s", e)
            return ToolResult(
                success=False,
                data="",
                error=f"Ошибка выполнения: {type(e).__name__}: {e}",
            )
        finally:
            sys.stdout = old_stdout
