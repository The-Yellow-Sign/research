"""Базовые классы для инструментов агента.

Определяет интерфейс BaseTool и модели данных для результатов.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Результат выполнения инструмента."""

    success: bool
    data: str = ""
    error: str | None = None


class ToolParameterType(str, Enum):
    """Типы параметров для JSON Schema."""

    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """Описание параметра инструмента."""

    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Any = None


class BaseTool(ABC):
    """Базовый класс для всех инструментов агента.

    Каждый инструмент должен определить:
    - name: уникальное имя для вызова
    - description: описание для LLM
    - parameters: список параметров
    - execute(): асинхронный метод выполнения
    """

    name: str
    description: str
    parameters: list[ToolParameter] = []

    def get_function_schema(self) -> dict[str, Any]:
        """Возвращает JSON Schema для Function Calling."""
        properties = {}
        required = []

        for param in self.parameters:
            properties[param.name] = {
                "type": param.type.value,
                "description": param.description,
            }
            if param.default is not None:
                properties[param.name]["default"] = param.default
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """Выполняет инструмент с заданными параметрами.

        Args:
            **kwargs: Параметры инструмента.

        Returns:
            ToolResult с результатом выполнения.

        """
        pass
