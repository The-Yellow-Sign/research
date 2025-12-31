"""FastAPI веб-API для RAG-сервиса.

Тонкая обёртка над RAGService, предоставляющая HTTP-эндпоинты.
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated, AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from opensearchpy.exceptions import ConnectionError as OpenSearchConnectionError
from pymilvus.exceptions import MilvusException

from src.application import RAGService
from src.application.dto import ChatRequest, ChatResponse
from src.config.logging_config import setup_logging
from src.config.telemetry import instrument_fastapi, setup_telemetry
from src.infrastructure.search import SearchEngine

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
        logger.critical(f"FATAL: Ошибка инициализации сервисов: {e}")


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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Эндпоинт проверки здоровья."""
    return {"status": "ok"}


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
async def chat(
    request: ChatRequest,
    service: RAGServiceDep,
) -> ChatResponse:
    """Обрабатывает чат-запрос через RAG-пайплайн."""
    try:
        response = await service.process_query(request)
        return response

    except (OpenSearchConnectionError, MilvusException) as e:
        logger.error(f"Ошибка подключения к БД: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Временная ошибка базы знаний. Попробуйте позже.",
        ) from e
    except ValueError as e:

        logger.warning(f"Ошибка валидации/данных: {e}")
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api:app",
        host="127.0.0.1",  # noqa: S104
        port=8000,
        reload=True,
    )
