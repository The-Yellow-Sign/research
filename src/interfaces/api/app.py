"""FastAPI веб-API для RAG-сервиса.

Обёртка над RAGService, предоставляющая HTTP-эндпоинты.
RFC 9457 Problem Details для структурированных ошибок.
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from pymilvus.exceptions import MilvusException

from src.application import RAGService
from src.application.dto import ChatRequest, ChatResponse
from src.config.logging_config import setup_logging
from src.config.settings import settings
from src.config.telemetry import instrument_fastapi, setup_telemetry
from src.infrastructure.resilience import CircuitOpenError
from src.infrastructure.search import SearchEngine
from src.interfaces.api.problem import ProblemDetail, create_problem

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Управление жизненным циклом приложения."""
    setup_logging()
    setup_telemetry()
    instrument_fastapi(app)
    try:
        logger.info("Запуск: инициализация SearchEngine...")
        search_engine = SearchEngine()
        app.state.search_engine = search_engine

        logger.info("Запуск: инициализация RAGService...")
        rag_service = RAGService(search_engine=search_engine)
        app.state.rag_service = rag_service

        logger.info("Все сервисы успешно инициализированы")
    except Exception as e:
        logger.critical("FATAL: Ошибка инициализации сервисов: %s", e)

        raise e

    yield

    logger.info("Завершение работы...")


app = FastAPI(
    title="DevOps RAG API",
    description="RAG-powered база знаний DevOps",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def problem_response(problem: ProblemDetail) -> JSONResponse:
    """Создаёт JSONResponse из ProblemDetail."""
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(),
        media_type="application/problem+json",
    )


@app.exception_handler(CircuitOpenError)
async def circuit_open_handler(request: Request, exc: CircuitOpenError) -> JSONResponse:
    """Обработчик открытого Circuit Breaker."""
    logger.warning("Circuit '%s' открыт, запрос отклонён", exc.circuit_name)
    problem = create_problem(
        "rag/llm-unavailable",
        f"Сервис {exc.circuit_name} временно недоступен. Повторите позже.",
        str(request.url),
    )
    return problem_response(problem)


@app.exception_handler(TimeoutError)
async def timeout_handler(request: Request, exc: TimeoutError) -> JSONResponse:
    """Обработчик таймаута."""
    logger.error("Таймаут запроса: %s", exc)
    problem = create_problem(
        "rag/llm-timeout",
        str(exc) or "Превышено время ожидания ответа",
        str(request.url),
    )
    return problem_response(problem)


@app.exception_handler(ValueError)
async def validation_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Обработчик ошибок валидации."""
    logger.warning("Ошибка валидации: %s", exc)
    problem = create_problem(
        "rag/invalid-request",
        str(exc),
        str(request.url),
    )
    return problem_response(problem)


@app.exception_handler(OpenSearchConnectionError)
@app.exception_handler(MilvusException)
async def db_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик ошибок подключения к БД."""
    logger.error("Ошибка подключения к БД: %s", exc)
    problem = create_problem(
        "rag/llm-unavailable",
        "Временная ошибка базы знаний. Попробуйте позже.",
        str(request.url),
    )
    return problem_response(problem)


def get_rag_service(request: Request) -> RAGService:
    """Dependency function для получения RAGService."""
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        logger.error("RAGService не инициализирован")
        raise ValueError("Сервис инициализируется или недоступен")
    return service


RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Эндпоинт проверки здоровья."""
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness_probe(request: Request) -> dict[str, str | dict[str, bool]]:
    """Проверяет готовность всех внешних сервисов."""
    checks: dict[str, bool] = {}

    search_engine = getattr(request.app.state, "search_engine", None)
    if search_engine:
        try:
            search_engine.opensearch_client.info()
            checks["opensearch"] = True
        except Exception:
            checks["opensearch"] = False

        try:
            _ = search_engine.milvus_collection.num_entities
            checks["milvus"] = True
        except Exception:
            checks["milvus"] = False
    else:
        checks["opensearch"] = False
        checks["milvus"] = False

    rag_service = getattr(request.app.state, "rag_service", None)
    if rag_service:
        try:
            checks["llm"] = await rag_service.llm_client.check_health()
        except Exception:
            checks["llm"] = False
    else:
        checks["llm"] = False

    all_healthy = all(checks.values())

    return {
        "status": "ready" if all_healthy else "degraded",
        "checks": checks,
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    service: RAGServiceDep,
) -> ChatResponse:
    """Обрабатывает чат-запрос через RAG-пайплайн."""
    response = await service.process_query(request)
    return response


if __name__ == "__main__":
    uvicorn.run(
        "src.interfaces.api.app:app",
        host="127.0.0.1",
        port=8080,
        reload=True,
        log_level="info",
    )
