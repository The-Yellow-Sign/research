"""Agent Tracer — трейсинг шагов агента.

Собирает метрики и события для observability.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TraceEvent:
    """Событие трейсинга."""

    event_type: str
    name: str
    start_time: float
    end_time: float = 0.0
    duration_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str | None = None


@dataclass
class AgentTrace:
    """Полный трейс выполнения агента."""

    trace_id: str
    query: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    events: list[TraceEvent] = field(default_factory=list)
    total_steps: int = 0
    tools_used: list[str] = field(default_factory=list)

    def add_event(self, event: TraceEvent) -> None:
        """Добавляет событие в трейс."""
        self.events.append(event)

    def finish(self) -> None:
        """Завершает трейс."""
        self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Конвертирует трейс в словарь."""
        return {
            "trace_id": self.trace_id,
            "query": self.query[:100],
            "total_duration_ms": (self.end_time - self.start_time) * 1000,
            "total_steps": self.total_steps,
            "tools_used": self.tools_used,
            "events": [
                {
                    "type": e.event_type,
                    "name": e.name,
                    "args": e.metadata.get("params"),
                    "result": e.metadata.get("result"),
                    "metadata": e.metadata,
                    "duration_ms": e.duration_ms,
                    "success": e.success,
                    "error": e.error,
                }
                for e in self.events
            ],
        }

    def get_summary(self) -> dict[str, Any]:
        """Возвращает краткую сводку."""
        tool_times = {}
        for e in self.events:
            if e.event_type == "tool_call":
                tool_times[e.name] = tool_times.get(e.name, 0) + e.duration_ms

        return {
            "trace_id": self.trace_id,
            "total_ms": round((self.end_time - self.start_time) * 1000, 2),
            "steps": self.total_steps,
            "tools": self.tools_used,
            "tool_times_ms": tool_times,
        }


class AgentTracer:
    """Трейсер для агентных вызовов."""

    def __init__(self) -> None:
        """Инициализирует трейсер."""
        self._current_trace: AgentTrace | None = None

    def start_trace(self, trace_id: str, query: str) -> AgentTrace:
        """Начинает новый трейс."""
        self._current_trace = AgentTrace(trace_id=trace_id, query=query)
        logger.info("[TRACE] Started: %s", trace_id)
        return self._current_trace

    def end_trace(self) -> AgentTrace | None:
        """Завершает текущий трейс."""
        if self._current_trace:
            self._current_trace.finish()
            summary = self._current_trace.get_summary()
            logger.info("[TRACE] Finished: %s", summary)
            trace = self._current_trace
            self._current_trace = None
            return trace
        return None

    def trace_tool_call(
        self,
        tool_name: str,
        params: dict[str, Any],
    ) -> "ToolCallContext":
        """Создаёт контекст для трейсинга tool call."""
        return ToolCallContext(self, tool_name, params)

    def trace_thinking(self) -> "ThinkingContext":
        """Создаёт контекст для трейсинга thinking."""
        return ThinkingContext(self)


class ToolCallContext:
    """Context manager для трейсинга tool calls."""

    def __init__(
        self,
        tracer: AgentTracer,
        tool_name: str,
        params: dict[str, Any],
    ) -> None:
        """Инициализирует контекст."""
        self.tracer = tracer
        self.tool_name = tool_name
        self.params = params
        self.start_time = 0.0
        self.result_data: str | None = None
        self.metadata: dict[str, Any] = {}

    def set_result(self, data: str) -> None:
        """Устанавливает результат выполнения (для трейса)."""
        self.result_data = data

    def update_metadata(self, **kwargs: Any) -> None:
        """Обновляет метаданные события."""
        self.metadata.update(kwargs)

    def __enter__(self) -> "ToolCallContext":
        """Начинает трейсинг."""
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Завершает трейсинг."""
        end_time = time.time()
        duration_ms = (end_time - self.start_time) * 1000

        event = TraceEvent(
            event_type="tool_call",
            name=self.tool_name,
            start_time=self.start_time,
            end_time=end_time,
            duration_ms=round(duration_ms, 2),
            metadata={
                "params": self.params,
                "result": self.result_data[:2000] if self.result_data else None,
                **self.metadata,
            },
            success=exc_type is None,
            error=str(exc_val) if exc_val else None,
        )

        if self.tracer._current_trace:
            self.tracer._current_trace.add_event(event)
            if self.tool_name not in self.tracer._current_trace.tools_used:
                self.tracer._current_trace.tools_used.append(self.tool_name)

        logger.debug("[TRACE] Tool %s: %.2fms", self.tool_name, duration_ms)


class ThinkingContext:
    """Context manager для трейсинга thinking phase."""

    def __init__(self, tracer: AgentTracer) -> None:
        """Инициализирует контекст."""
        self.tracer = tracer
        self.start_time = 0.0
        self.result_data: str | None = None

    def set_result(self, data: str) -> None:
        """Устанавливает результат (мысль агента)."""
        self.result_data = data

    def __enter__(self) -> "ThinkingContext":
        """Начинает трейсинг."""
        self.start_time = time.time()
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: Exception | None,
        exc_tb: Any,
    ) -> None:
        """Завершает трейсинг."""
        end_time = time.time()
        duration_ms = (end_time - self.start_time) * 1000

        event = TraceEvent(
            event_type="thinking",
            name="llm_think",
            start_time=self.start_time,
            end_time=end_time,
            duration_ms=round(duration_ms, 2),
            metadata={
                "result": self.result_data[:2000] if self.result_data else None,
            },
            success=exc_type is None,
            error=str(exc_val) if exc_val else None,
        )

        if self.tracer._current_trace:
            self.tracer._current_trace.add_event(event)
            self.tracer._current_trace.total_steps += 1

        logger.debug("[TRACE] Thinking: %.2fms", duration_ms)
