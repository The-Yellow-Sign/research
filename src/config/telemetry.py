"""OpenTelemetry трейсинг для приложения.

Настраивает автоматическую инструментацию FastAPI и кастомные спаны.
"""

import logging
from contextlib import contextmanager
from typing import Any, Generator

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Span, Status, StatusCode

from src.config.settings import settings

logger = logging.getLogger(__name__)


_tracer: trace.Tracer | None = None


def setup_telemetry() -> None:
    """Настраивает OpenTelemetry трейсинг.

    Если OTLP_ENDPOINT не задан, использует ConsoleSpanExporter для отладки.
    """
    global _tracer

    resource = Resource.create(
        {
            "service.name": settings.otlp_service_name,
            "service.version": "1.0.0",
            "deployment.environment": settings.environment,
        }
    )

    provider = TracerProvider(resource=resource)

    if settings.otlp_endpoint:
        try:
            exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTLP трейсинг включён: %s", settings.otlp_endpoint)
        except Exception as e:
            logger.warning("Не удалось настроить OTLP: %s. Используем console exporter.", e)
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    elif settings.environment == "development":
        logger.debug("Трейсинг в режиме development (без экспорта)")
    else:
        logger.info("Трейсинг отключён (OTLP_ENDPOINT не задан)")

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)


def get_tracer() -> trace.Tracer:
    """Возвращает глобальный tracer."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer


@contextmanager
def traced_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Контекстный менеджер для создания спана.

    Args:
        name: Название операции.
        attributes: Дополнительные атрибуты спана.

    Yields:
        Span объект для добавления дополнительных данных.

    Example:
        with traced_operation("llm.generate_answer", {"model": "qwen"}) as span:
            result = await generate_answer()
            span.set_attribute("response_length", len(result))

    """
    tracer = get_tracer()
    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def instrument_fastapi(app: Any) -> None:
    """Инструментирует FastAPI приложение.

    Args:
        app: FastAPI application instance.

    """
    try:
        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI инструментирован для трейсинга")
    except Exception as e:
        logger.warning("Не удалось инструментировать FastAPI: %s", e)
