"""RFC 9457 Problem Details — структурированные HTTP-ошибки.

Реализует стандарт RFC 9457 для единообразных ошибок API.
"""

from typing import Literal

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """RFC 9457 Problem Detail.

    Стандартный формат HTTP-ошибок для REST API.

    Attributes:
        type: URI-идентификатор типа ошибки.
        title: Краткое описание ошибки.
        status: HTTP-статус код.
        detail: Подробное описание для конкретного случая.
        instance: URI запроса, вызвавшего ошибку.

    """

    type: str = Field(..., description="URI типа ошибки")
    title: str = Field(..., description="Краткое описание")
    status: int = Field(..., description="HTTP статус код")
    detail: str = Field(..., description="Детальное описание")
    instance: str = Field(default="", description="URI запроса")


ProblemType = Literal[
    "rag/invalid-request",
    "rag/no-documents",
    "rag/llm-unavailable",
    "rag/llm-timeout",
    "rag/internal-error",
]


PROBLEM_CATALOG: dict[ProblemType, tuple[int, str]] = {
    "rag/invalid-request": (400, "Невалидный запрос"),
    "rag/no-documents": (404, "Документы не найдены"),
    "rag/llm-unavailable": (503, "LLM сервис недоступен"),
    "rag/llm-timeout": (504, "Превышено время ожидания LLM"),
    "rag/internal-error": (500, "Внутренняя ошибка сервера"),
}


def create_problem(
    problem_type: ProblemType,
    detail: str,
    instance: str = "",
) -> ProblemDetail:
    """Создаёт ProblemDetail по типу ошибки.

    Args:
        problem_type: Тип ошибки из каталога.
        detail: Детальное описание конкретного случая.
        instance: URI запроса (опционально).

    Returns:
        ProblemDetail с заполненными полями.

    """
    status, title = PROBLEM_CATALOG[problem_type]
    return ProblemDetail(
        type=problem_type,
        title=title,
        status=status,
        detail=detail,
        instance=instance,
    )
