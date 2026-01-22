"""FastAPI веб-API для RAG-сервиса.

Обёртка над RAGService, предоставляющая HTTP-эндпоинты.
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from pymilvus.exceptions import MilvusException

from src.application.dto import ChatRequest, ChatResponse
from src.application.services import RAGService
from src.application.services.tool_factory import create_default_tools
from src.application.use_cases.agent_controller import AgentController
from src.config.logging_config import setup_logging
from src.config.settings import settings
from src.config.telemetry import instrument_fastapi, setup_telemetry
from src.infrastructure.llm.client import LLMClient
from src.infrastructure.search import SearchEngine
from src.interfaces.api.metrics import get_metrics, get_metrics_content_type, track_request

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

        logger.info("Запуск: инициализация LLMClient...")
        llm_client = LLMClient()

        logger.info("Запуск: инициализация RAGService...")
        rag_service = RAGService(llm_client=llm_client, search_engine=search_engine)
        app.state.rag_service = rag_service

        logger.info("Запуск: инициализация AgentController...")
        tools = create_default_tools(search_engine=search_engine, llm_client=llm_client)
        app.state.agent_controller = AgentController(llm=llm_client, tools=tools)

        logger.info("Все сервисы успешно инициализированы")
    except Exception as e:
        logger.critical("FATAL: Ошибка инициализации сервисов: %s", e)

        raise e

    yield

    logger.info("Завершение работы...")

    try:
        from pymilvus import connections

        if connections.has_connection("default"):
            connections.disconnect("default")
            logger.info("Milvus connection closed")
    except Exception as e:
        logger.warning("Error closing Milvus: %s", e)

    try:
        search_engine = getattr(app.state, "search_engine", None)
        if search_engine and hasattr(search_engine, "opensearch_client"):
            search_engine.opensearch_client.close()
            logger.info("OpenSearch connection closed")
    except Exception as e:
        logger.warning("Error closing OpenSearch: %s", e)


app = FastAPI(
    title="DevOps RAG API",
    description="""
## Agentic RAG API для DevOps документации

### Возможности:
- **RAG Search** — поиск по базе знаний
- **Agent Chat** — ReAct агент с инструментами
- **Observability** — трейсинг и метрики

### Endpoints:
- `/chat` — простой RAG чат
- `/agent/chat` — агентный чат с reasoning
- `/metrics` — Prometheus метрики
""",
    version="2.0.0",
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Проверки здоровья сервиса"},
        {"name": "rag", "description": "RAG поиск и чат"},
        {"name": "agent", "description": "Агентный чат с ReAct"},
        {"name": "metrics", "description": "Prometheus метрики"},
    ],
    contact={
        "name": "DevOps RAG Team",
        "email": "support@devops-rag.local",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


def get_rag_service(request: Request) -> RAGService:
    """Dependency function для получения RAGService."""
    service = getattr(request.app.state, "rag_service", None)
    if service is None:
        logger.error("RAGService не инициализирован")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Сервис инициализируется или недоступен.",
        )
    return service


RAGServiceDep = Annotated[RAGService, Depends(get_rag_service)]


@app.get("/health/live", tags=["health"])
async def liveness_probe() -> dict[str, str]:
    """Kubernetes liveness probe — проверяет что процесс жив."""
    return {"status": "alive"}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Эндпоинт проверки здоровья."""
    return {"status": "ok"}


@app.get("/metrics", tags=["metrics"])
async def prometheus_metrics():
    """Prometheus метрики для мониторинга."""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type(),
    )


@app.get("/health/ready")
async def readiness_probe(request: Request) -> dict[str, str | dict[str, bool]]:
    """Проверяет готовность всех внешних сервисов.

    Returns:
        Статус сервисов: Milvus, OpenSearch, LLM API.

    """
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
@track_request("chat")
async def chat(
    request: ChatRequest,
    service: RAGServiceDep,
) -> ChatResponse:
    """Обрабатывает чат-запрос через RAG-пайплайн."""
    try:
        response = await service.process_query(request)
        return response

    except (OpenSearchConnectionError, MilvusException) as e:
        logger.error("Ошибка подключения к БД: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка базы знаний. Попробуйте позже.",
        ) from e
    except ValueError as e:
        logger.warning("Ошибка валидации/данных: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.exception("Непредвиденная ошибка обработки запроса")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера.",
        ) from e


def get_agent_controller(request: Request) -> AgentController:
    """Dependency для AgentController."""
    controller = getattr(request.app.state, "agent_controller", None)
    if controller is None:
        logger.error("AgentController не инициализирован")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Агент не инициализирован.",
        )
    return controller


AgentControllerDep = Annotated[AgentController, Depends(get_agent_controller)]


@app.post("/agent/chat")
@track_request("agent_chat")
async def agent_chat(
    request: ChatRequest,
    controller: AgentControllerDep,
) -> dict:
    """Агентный чат с ReAct loop."""
    try:
        response = await controller.run(
            query=request.query,
            history=request.history,
        )
        return {
            "answer": response.answer,
            "sources": response.sources,
            "steps": response.steps,
            "total_time_sec": response.total_time_sec,
            "trace": response.trace,
        }
    except Exception as e:
        logger.exception("Agent chat error")

        if isinstance(e, (OpenSearchConnectionError, MilvusException)):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Временная ошибка базы знаний. Попробуйте позже.",
            ) from e

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка агента. Попробуйте позже.",
        ) from e


@app.post("/agent/chat/stream")
@track_request("agent_chat_stream")
async def agent_chat_stream(
    request: ChatRequest,
    controller: AgentControllerDep,
):
    """Агентный чат со streaming (SSE)."""

    async def generate():
        try:
            async for event in controller.run_stream(
                query=request.query,
                history=request.history,
            ):
                yield f"data: {event.json()}\n\n"
        except Exception as e:
            logger.exception("Agent stream error")
            yield f'data: {{"type": "error", "content": "{e}"}}\n\n'

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    uvicorn.run(
        "src.interfaces.api.app:app",
        host="0.0.0.0",  # noqa: S104
        port=8080,
        reload=True,
        log_level="info",
    )
